"use strict";
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const {execFile}=require('node:child_process');const {promisify}=require('node:util');
const {assertPlain,safePath,atomicWrite,digest}=require('./storage-paths.cjs');
const VERSION=/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$/;
function version(value){if(typeof value!=='string'||value.length>100||!VERSION.test(value))throw Error('upgrade_invalid_version');if(VERSION.exec(value)[4]?.split('.').some(part=>/^0\d+$/.test(part)))throw Error('upgrade_invalid_version');return value;}
function compareVersions(left,right){const a=VERSION.exec(version(left)),b=VERSION.exec(version(right));for(let i=1;i<=3;i++){const x=BigInt(a[i]),y=BigInt(b[i]);if(x!==y)return x>y?1:-1;}if(a[4]===b[4])return 0;if(!a[4])return 1;if(!b[4])return -1;const x=a[4].split('.'),y=b[4].split('.');for(let i=0;i<Math.max(x.length,y.length);i++){if(x[i]===undefined)return -1;if(y[i]===undefined)return 1;if(x[i]===y[i])continue;const xn=/^\d+$/.test(x[i]),yn=/^\d+$/.test(y[i]);if(xn&&yn)return BigInt(x[i])>BigInt(y[i])?1:-1;if(xn!==yn)return xn?-1:1;return x[i]>y[i]?1:-1;}return 0;}
function absolute(value){if(typeof value!=='string'||!path.isAbsolute(value)||/[\x00-\x1f]/.test(value))throw Error('upgrade_unsafe_path');return path.resolve(value);}
const SNAPSHOT=`import sqlite3,sys,json,pathlib
source=sqlite3.connect(pathlib.Path(sys.argv[1]).resolve().as_uri()+'?mode=ro',uri=True,timeout=30)
target=sqlite3.connect(sys.argv[2],timeout=30)
try:
 source.backup(target)
 if target.execute('PRAGMA quick_check').fetchone()[0]!='ok': raise RuntimeError('snapshot_integrity_failed')
 schema={'userVersion':target.execute('PRAGMA user_version').fetchone()[0]}
 if target.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='flyway_schema_history'").fetchone()[0]:
  row=target.execute('SELECT version FROM flyway_schema_history WHERE success=1 ORDER BY installed_rank DESC LIMIT 1').fetchone()
  if row and row[0] is not None: schema['flywayVersion']=str(row[0])
 target.commit()
 print(json.dumps(schema))
finally:
 target.close()
 source.close()
`;
class UpgradeGuard {
 constructor({dataDir,version:current,executable,python,ensureStopped,run=promisify(execFile)}){this.dataDir=absolute(dataDir);this.version=version(current);this.executable=absolute(executable);this.python=absolute(python);this.ensureStopped=ensureStopped;this.run=run;this.busy=false;}
 async _path(relative){return safePath(this.dataDir,relative);}
 async _exists(file){await assertPlain(file);try{const stat=await fs.stat(file);if(!stat.isFile())throw Error('upgrade_special_file');return stat;}catch(error){if(error.code==='ENOENT')return null;throw error;}}
 async _state(){const file=await this._path('runtime/package-state.json');if(!await this._exists(file))return {format:'framewise-package-state',schemaVersion:1};const raw=await fs.readFile(file,'utf8');if(raw.length>32768)throw Error('upgrade_invalid_state');let state;try{state=JSON.parse(raw);}catch{throw Error('upgrade_invalid_state');}if(!state||state.format!=='framewise-package-state'||state.schemaVersion!==1)throw Error('upgrade_invalid_state');if(state.ready){version(state.ready.version);absolute(state.ready.executable);}if(state.pending){const p=state.pending;if(typeof p.id!=='string'||!/^upgrade-[a-f0-9-]{36}$/.test(p.id)||p.backupRelative!==`backups/${p.id}`||!/^([a-f0-9]{64})$/.test(p.sha256)||!Number.isSafeInteger(p.size)||p.size<=0)throw Error('upgrade_invalid_state');version(p.toVersion);if(p.fromVersion)version(p.fromVersion);if(p.previousExecutable)absolute(p.previousExecutable);}return state;}
 async _write(state){await atomicWrite(await this._path('runtime/package-state.json'),JSON.stringify(state,null,2));}
 async _stopped(){if(typeof this.ensureStopped!=='function'||await this.ensureStopped()!==true)throw Error('runtime_not_stopped');}
 async _log(stage,result,started,request,error){try{const file=await this._path('logs/native-upgrade.jsonl');await fs.mkdir(path.dirname(file),{recursive:true});const stat=await this._exists(file);if(stat?.size>1024*1024){const previous=await this._path('logs/native-upgrade.jsonl.1');await fs.rm(previous,{force:true});await fs.rename(file,previous);}await fs.appendFile(file,JSON.stringify({timestamp:new Date().toISOString(),event:'native_upgrade',stage,result,version:this.version,requestId:request,elapsedMs:Date.now()-started,...(error?{errorType:/^[a-z_]+$/.test(error.message)?error.message:error.name}: {})})+'\n',{mode:0o600});}catch{}}
 async _action(stage,action){if(this.busy)throw Error('upgrade_operation_running');this.busy=true;const started=Date.now(),request=crypto.randomUUID();try{const result=await action();await this._log(stage,'completed',started,request);return result;}catch(error){await this._log(stage,'failed',started,request,error);throw error;}finally{this.busy=false;}}
 async _verified(pending){const directory=await this._path(pending.backupRelative),file=await safePath(directory,'framewise.db'),manifest=await safePath(directory,'manifest.json');if(!await this._exists(manifest))throw Error('upgrade_backup_invalid');const raw=await fs.readFile(manifest,'utf8');if(raw.length>32768)throw Error('upgrade_backup_invalid');let record;try{record=JSON.parse(raw);}catch{throw Error('upgrade_backup_invalid');}const stat=await this._exists(file);if(record.format!=='framewise-upgrade-backup'||record.id!==pending.id||record.sha256!==pending.sha256||record.size!==pending.size||!stat||stat.size!==pending.size||await digest(file)!==pending.sha256)throw Error('upgrade_backup_invalid');return {directory,file};}
 async beforeStart(){return this._action('before_start',async()=>{
  await this._stopped();const state=await this._state(),database=await this._path('database/framewise.db'),exists=await this._exists(database);
  if(exists&&(state.ready&&compareVersions(state.ready.version,this.version)>0||state.pending&&!state.pending.rolledBackAt&&compareVersions(state.pending.toVersion,this.version)>0))throw Error('upgrade_data_newer_than_app');
  if(state.pending){if(state.pending.toVersion!==this.version&&!state.pending.rolledBackAt)throw Error('upgrade_pending_other_version');if(state.pending.toVersion===this.version){await this._verified(state.pending);if(state.pending.rolledBackAt){delete state.pending.rolledBackAt;await this._write(state);}return {backup:true,reused:true,backupId:state.pending.id};}}
  if(!exists||state.ready?.version===this.version)return {backup:false};
  const id=`upgrade-${crypto.randomUUID()}`,relative=`backups/${id}`,directory=await this._path(relative);await fs.mkdir(directory,{recursive:true});const target=await safePath(directory,'framewise.db');
  await assertPlain(this.python);let response;try{response=await this.run(this.python,['-I','-c',SNAPSHOT,database,target],{windowsHide:true,timeout:120000,maxBuffer:32768});}catch{throw Error('upgrade_snapshot_failed');}let schema;try{schema=JSON.parse(response.stdout);}catch{throw Error('upgrade_snapshot_failed');}
  if(!Number.isSafeInteger(schema.userVersion)||schema.userVersion<0||schema.flywayVersion!==undefined&&(typeof schema.flywayVersion!=='string'||!/^[0-9._-]{1,100}$/.test(schema.flywayVersion)))throw Error('upgrade_snapshot_failed');
  const stat=await this._exists(target);if(!stat||stat.size<=0)throw Error('upgrade_snapshot_failed');const sha256=await digest(target),pending={id,backupRelative:relative,toVersion:this.version,...(state.ready?{fromVersion:state.ready.version,previousExecutable:state.ready.executable}:{}),sha256,size:stat.size,schema,createdAt:new Date().toISOString()};
  await atomicWrite(await safePath(directory,'manifest.json'),JSON.stringify({format:'framewise-upgrade-backup',...pending},null,2));state.pending=pending;await this._write(state);return {backup:true,backupId:id};
 });}
 async confirm(){return this._action('confirm',async()=>{const state=await this._state();if(state.ready&&compareVersions(state.ready.version,this.version)>0)throw Error('upgrade_data_newer_than_app');if(state.pending&&state.pending.toVersion!==this.version)throw Error('upgrade_pending_other_version');state.ready={version:this.version,executable:this.executable,confirmedAt:new Date().toISOString()};delete state.pending;await this._write(state);return {ready:true};});}
 async rollback(){return this._action('rollback',async()=>{
  await this._stopped();const state=await this._state();if(!state.pending)return {restored:false};if(state.pending.toVersion!==this.version)throw Error('upgrade_pending_other_version');const verified=await this._verified(state.pending),database=await this._path('database/framewise.db');await fs.mkdir(path.dirname(database),{recursive:true});
  const id=crypto.randomUUID(),staged=await this._path(`database/rollback-${id}.tmp`),moves=[];
  await fs.copyFile(verified.file,staged,require('node:fs').constants.COPYFILE_EXCL);if(await digest(staged)!==state.pending.sha256){await fs.rm(staged,{force:true});throw Error('upgrade_backup_invalid');}
  try{
   // Keep the failed main file, then atomically replace it without a missing-database window.
   if(await this._exists(database))await fs.copyFile(database,await safePath(verified.directory,`failed-${id}-framewise.db`),require('node:fs').constants.COPYFILE_EXCL);
   for(const suffix of ['-wal','-shm']){const live=await this._path(`database/framewise.db${suffix}`);if(await this._exists(live)){const archived=await safePath(verified.directory,`failed-${id}-framewise.db${suffix}`);await fs.rename(live,archived);moves.push({live,archived});}}
   await fs.rename(staged,database);
  }catch(error){for(const move of moves.reverse())await fs.rename(move.archived,move.live);await fs.rm(staged,{force:true});throw error;}
  state.pending.rolledBackAt=new Date().toISOString();await this._write(state);return {restored:true,backupId:state.pending.id};
 });}
 async previousExecutable(){const state=await this._state(),previous=state.pending?.previousExecutable;if(!previous)return null;const current=this.executable.split(path.sep),prior=absolute(previous).split(path.sep),index=current.lastIndexOf('versions');if(index<1||prior[index]!=='versions'||current.slice(0,index+1).join(path.sep).toLowerCase()!==prior.slice(0,index+1).join(path.sep).toLowerCase()||current[index+1]===prior[index+1]||path.basename(previous).toLowerCase()!=='framewise.exe')return null;try{version(current[index+1]);version(prior[index+1]);if(prior[index+1]!==state.pending.fromVersion||!await this._exists(previous))return null;return path.resolve(previous);}catch{return null;}}
}
module.exports={UpgradeGuard,compareVersions};
