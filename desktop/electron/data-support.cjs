'use strict';
const fs=require('node:fs/promises');
const path=require('node:path');
const crypto=require('node:crypto');
const {assertPlain,safePath,relativeName,atomicWrite,digest,walk}=require('./storage-paths.cjs');
const PROFILE_STORES=['IndexedDB','Local Storage','Session Storage','media-library.json'];
const DATA_STORES=['database','keyframes'];
const METADATA_KEYS=['appVersion','runtimeVersion','platform','arch','device','modelStatus','gpuAvailable','encryptionAvailable'];
const EVENT_KEYS=['timestamp','event','stage','status','errorType','requestId','taskId','durationMs','elapsedMs','httpStatus','inputTokens','outputTokens'];
function safeScalar(value) {
  if(typeof value==='number')return Number.isFinite(value)&&value>=0?value:undefined;
  if(typeof value==='boolean')return value;
  if(typeof value==='string'&&value.length<=100&&/^[A-Za-z0-9_.:+ -]+$/.test(value)&&!/(?:sk-|bearer|api.?key|authorization|password|token[=:])/i.test(value))return value;
  return undefined;
}
function pickSafe(value,keys) {const output={};for(const key of keys){const clean=safeScalar(value?.[key]);if(clean!==undefined)output[key]=clean;}return output;}
async function removeTree(target) {await assertPlain(target);try{const stat=await fs.stat(target);if(stat.isDirectory())await walk(target);await fs.rm(target,{recursive:true,force:true});}catch(error){if(error.code!=='ENOENT')throw error;}}
function inside(parent,child) {const rel=path.relative(path.resolve(parent),path.resolve(child));return !rel||(!rel.startsWith(`..${path.sep}`)&&rel!=='..'&&!path.isAbsolute(rel));}
class DataSupport {
  constructor({storage,ensureStopped,profileRoot,profileStopped}) {
    this.storage=storage;this.root=storage.root;this.profileRoot=profileRoot?path.resolve(profileRoot):null;this.ensureStopped=ensureStopped;this.profileStopped=profileStopped;this.busy=false;
  }
  async _exclusive(action) {if(this.busy)throw Error('data_operation_running');this.busy=true;try{if(typeof this.ensureStopped!=='function')throw Error('quiescence_required');if(await this.ensureStopped()!==true)throw Error('runtime_not_stopped');return await action();}finally{this.busy=false;}}
  _external(target) {if(typeof target!=='string'||!path.isAbsolute(target))throw Error('absolute_destination_required');const resolved=path.resolve(target);if(inside(this.root,resolved)||inside(resolved,this.root)||(this.profileRoot&&(inside(this.profileRoot,resolved)||inside(resolved,this.profileRoot))))throw Error('overlapping_backup_path');return resolved;}
  async _exists(target) {try{await assertPlain(target);return await fs.stat(target);}catch(error){if(error.code==='ENOENT')return null;throw error;}}
  async _copy(source,destination,files,prefix) {
    await assertPlain(source);const stat=await fs.stat(source);
    const entries=stat.isDirectory()?await walk(source):[{relative:'',file:source}];
    if(stat.isDirectory())await fs.mkdir(destination,{recursive:true});
    for(const entry of entries) {
      const target=entry.relative?await safePath(destination,entry.relative):destination;
      await assertPlain(target);await fs.mkdir(path.dirname(target),{recursive:true});await fs.copyFile(entry.file,target,require('node:fs').constants.COPYFILE_EXCL);
      files.push({path:entry.relative?`${prefix}/${entry.relative}`:prefix,size:(await fs.stat(target)).size,sha256:await digest(target)});
    }
  }
  async backup({destination,includeModels=false,notesSnapshot}) {
    return this._exclusive(async()=>{
      const target=this._external(destination);await assertPlain(target);if(await this._exists(target))throw Error('backup_destination_exists');
      const stage=`${target}.${crypto.randomUUID()}.tmp`;await assertPlain(stage);await fs.mkdir(stage,{recursive:true});
      try {
        const manifest={format:'framewise-backup',version:1,createdAt:new Date().toISOString(),schemaVersion:1,stores:[],files:[],includesModels:!!includeModels};
        for(const name of [...DATA_STORES,...(includeModels?['models']:[])]) {
          const source=await safePath(this.root,name);if(!await this._exists(source))continue;
          const store=`data/${name}`;await this._copy(source,await safePath(stage,store),manifest.files,store);manifest.stores.push(store);
        }
        if(notesSnapshot!==undefined){
          if(notesSnapshot?.format!=='framewise-renderer'||notesSnapshot.version!==1||!Array.isArray(notesSnapshot.notes)||!notesSnapshot.localStorage||typeof notesSnapshot.localStorage!=='object'||Array.isArray(notesSnapshot.localStorage))throw Error('invalid_notes_snapshot');
          const snapshot=JSON.stringify(notesSnapshot,(key,value)=>{if(['__proto__','constructor','prototype'].includes(key)||typeof value==='function'||typeof value==='bigint'||(typeof value==='number'&&!Number.isFinite(value)))throw Error('invalid_notes_snapshot');return value;});
          if(typeof snapshot!=='string'||Buffer.byteLength(snapshot)>128*1024*1024||notesSnapshot===null||typeof notesSnapshot!=='object')throw Error('invalid_notes_snapshot');
          const snapshotFile=await safePath(stage,'app-notes.json');await atomicWrite(snapshotFile,snapshot);manifest.files.push({path:'app-notes.json',size:Buffer.byteLength(snapshot),sha256:await digest(snapshotFile)});manifest.stores.push('app-notes.json');
        }
        const profileIsStopped=typeof this.profileStopped==='function'&&await this.profileStopped()===true;
        if(notesSnapshot===undefined&&this.profileRoot&&!profileIsStopped)throw Error('notes_snapshot_required');
        if(this.profileRoot)for(const name of (notesSnapshot===undefined&&profileIsStopped?PROFILE_STORES:['media-library.json'])){
          const source=await safePath(this.profileRoot,name);if(!await this._exists(source))continue;
          const store=`profile/${name}`;await this._copy(source,await safePath(stage,store),manifest.files,store);manifest.stores.push(store);
        }
        await atomicWrite(path.join(stage,'manifest.json'),JSON.stringify(manifest,null,2));
        await fs.rename(stage,target);return {path:target,files:manifest.files.length,includesModels:manifest.includesModels};
      }catch(error){await removeTree(stage);throw error;}
    });
  }
  async _validate(source) {
    await assertPlain(source);const manifestPath=await safePath(source,'manifest.json');if((await fs.stat(manifestPath)).size>16*1024*1024)throw Error('backup_manifest_too_large');const raw=await fs.readFile(manifestPath,'utf8');if(raw.length>16*1024*1024)throw Error('backup_manifest_too_large');
    const manifest=JSON.parse(raw);if(manifest.format!=='framewise-backup'||manifest.version!==1||manifest.schemaVersion!==1||!Array.isArray(manifest.files)||!Array.isArray(manifest.stores)||manifest.files.length>100000)throw Error('invalid_backup');
    const permitted=new Set(['app-notes.json',...[...DATA_STORES,'models'].map(n=>`data/${n}`),...PROFILE_STORES.map(n=>`profile/${n}`)]);
    if(new Set(manifest.stores).size!==manifest.stores.length||manifest.stores.some(s=>!permitted.has(s)))throw Error('invalid_backup_store');
    if(manifest.stores.some(s=>s.startsWith('profile/'))&&!this.profileRoot)throw Error('profile_root_required');
    const seen=new Set();
    for(const file of manifest.files) {
      relativeName(file.path);
      if(seen.has(file.path.toLowerCase())||!Number.isSafeInteger(file.size)||file.size<0||!/^[a-f0-9]{64}$/.test(file.sha256)||!manifest.stores.some(store=>file.path===store||file.path.startsWith(`${store}/`)))throw Error('invalid_backup_file');
      const full=await safePath(source,file.path);const stat=await fs.stat(full);if(!stat.isFile()||stat.size!==file.size||await digest(full)!==file.sha256)throw Error('backup_checksum_mismatch');seen.add(file.path.toLowerCase());
    }
    const actual=await walk(source);if(actual.some(f=>f.relative!=='manifest.json'&&!seen.has(f.relative.toLowerCase()))||actual.length!==seen.size+1)throw Error('unexpected_backup_file');
    for(const store of manifest.stores){const stat=await this._exists(await safePath(source,store));if(!stat)throw Error('missing_backup_store');const fileStore=store==='app-notes.json'||store==='profile/media-library.json';if(fileStore?!stat.isFile():!stat.isDirectory())throw Error('invalid_backup_store_type');if(store==='app-notes.json'&&stat.size>128*1024*1024)throw Error('notes_snapshot_too_large');}
    return manifest;
  }
  async _identity(target) {
    const stat=await this._exists(target);if(!stat)return null;
    if(stat.isFile())return crypto.createHash('sha256').update(`file:${stat.size}:${await digest(target)}`).digest('hex');
    if(!stat.isDirectory())throw Error('special_file_forbidden');
    const entries=await walk(target);const records=[];
    for(const entry of entries)records.push([entry.relative,(await fs.stat(entry.file)).size,await digest(entry.file)]);
    records.sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:0);
    return crypto.createHash('sha256').update(JSON.stringify({type:'directory',files:records})).digest('hex');
  }
  async _writeJournal(transaction,journal) {
    const file=await safePath(transaction,'transaction.json');
    const temporary=await safePath(transaction,`transaction.${crypto.randomUUID()}.tmp`);
    const handle=await fs.open(temporary,'wx',0o600);
    try{await handle.writeFile(JSON.stringify(journal,null,2));await handle.sync();}finally{await handle.close();}
    await assertPlain(file);await fs.rename(temporary,file);
    // Flush directory metadata where supported; Windows denies directory handles.
    let directory;
    try{directory=await fs.open(transaction,'r');await directory.sync();}
    catch(error){if(!['EPERM','EACCES','EISDIR','EINVAL','ENOTSUP'].includes(error.code))throw error;}
    finally{if(directory)await directory.close();}
  }
  async _transaction(rollbackPath) {
    if(typeof rollbackPath!=='string'||!path.isAbsolute(rollbackPath))throw Error('invalid_rollback_path');
    const relative=path.relative(this.root,path.resolve(rollbackPath)).split(path.sep).join('/');
    if(!/^backups\/restore-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(relative))throw Error('invalid_rollback_path');
    const transaction=await safePath(this.root,relative);
    const journalFile=await safePath(transaction,'transaction.json');
    if((await fs.stat(journalFile)).size>1024*1024)throw Error('invalid_rollback');
    const journal=JSON.parse(await fs.readFile(journalFile,'utf8'));
    const phases=['staging','prepared','applying','applied','committed','rolling_back','rolled_back'];
    if(journal.format!=='framewise-restore-rollback'||journal.version!==2||!phases.includes(journal.phase)||!Array.isArray(journal.stores)||journal.stores.length>20||new Set(journal.stores.map(s=>s.store)).size!==journal.stores.length||new Set(journal.stores.map(s=>s.index)).size!==journal.stores.length)throw Error('invalid_rollback');
    const allowed=new Set([...DATA_STORES,'models'].map(n=>`data/${n}`).concat(PROFILE_STORES.map(n=>`profile/${n}`)));
    for(const item of journal.stores){
      if(!allowed.has(item.store)||!Number.isSafeInteger(item.index)||item.index<0||item.index>20||typeof item.hadPrevious!=='boolean'||(item.hadPrevious?!/^[a-f0-9]{64}$/.test(item.originalIdentity):item.originalIdentity!==null)||!/^[a-f0-9]{64}$/.test(item.incomingIdentity))throw Error('invalid_rollback');
    }
    return {transaction,journal};
  }
  async _operation(transaction,item) {
    const [scope,...parts]=item.store.split('/');
    if(scope==='profile'&&!this.profileRoot)throw Error('profile_root_required');
    if(scope==='profile'&&parts[0]!=='media-library.json'&&!(typeof this.profileStopped==='function'&&await this.profileStopped()===true))throw Error('profile_not_stopped');
    return {...item,destination:await safePath(scope==='data'?this.root:this.profileRoot,parts.join('/')),incoming:await safePath(transaction,`incoming-${item.index}`),previous:await safePath(transaction,`previous-${item.index}`),replaced:await safePath(transaction,`replaced-${item.index}`)};
  }
  async restore({source,onPrepared}) {
    return this._exclusive(async()=>{
      // A pending earlier restore must be resolved before creating another data generation.
      const backups=await safePath(this.root,'backups');
      if(await this._exists(backups))for(const entry of await fs.readdir(backups,{withFileTypes:true})){
        if(!/^restore-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(entry.name))continue;
        const rollbackPath=path.join(backups,entry.name);let previous;
        try{previous=(await this._transaction(rollbackPath)).journal;}
        catch(error){const failure=Error('restore_recovery_required');failure.recoveryPath=rollbackPath;failure.reason=error.code||error.message;throw failure;}
        if(!['committed','rolled_back'].includes(previous.phase)){const failure=Error('pending_restore_requires_recovery');failure.recoveryPath=rollbackPath;throw failure;}
      }
      const origin=this._external(source);const manifest=await this._validate(origin);
      if(onPrepared!==undefined&&typeof onPrepared!=='function')throw Error('invalid_prepared_callback');
      if(manifest.stores.some(store=>store.startsWith('profile/')&&store!=='profile/media-library.json')&&!(typeof this.profileStopped==='function'&&await this.profileStopped()===true))throw Error('profile_not_stopped');
      let notesSnapshot;
      if(manifest.stores.includes('app-notes.json')){const bytes=await fs.readFile(await safePath(origin,'app-notes.json'));const expected=manifest.files.find(f=>f.path==='app-notes.json');if(!expected||crypto.createHash('sha256').update(bytes).digest('hex')!==expected.sha256)throw Error('backup_changed_during_restore');notesSnapshot=JSON.parse(bytes.toString('utf8'));if(notesSnapshot?.format!=='framewise-renderer'||notesSnapshot.version!==1||!Array.isArray(notesSnapshot.notes)||!notesSnapshot.localStorage||typeof notesSnapshot.localStorage!=='object'||Array.isArray(notesSnapshot.localStorage))throw Error('invalid_notes_snapshot');}
      const transaction=await safePath(this.root,`backups/restore-${crypto.randomUUID()}`);await fs.mkdir(transaction,{recursive:true});
      const journal={format:'framewise-restore-rollback',version:2,phase:'staging',createdAt:new Date().toISOString(),stores:[]};
      await this._writeJournal(transaction,journal);
      try {
        for(const [index,store] of manifest.stores.entries()) {
          if(store==='app-notes.json')continue;
          const [scope,...parts]=store.split('/');const destination=await safePath(scope==='data'?this.root:this.profileRoot,parts.join('/'));
          const incoming=await safePath(transaction,`incoming-${index}`);
          const copied=[];await this._copy(await safePath(origin,store),incoming,copied,store);
          const expected=manifest.files.filter(f=>f.path===store||f.path.startsWith(`${store}/`));
          if(copied.length!==expected.length||copied.some(f=>!expected.some(e=>e.path===f.path&&e.size===f.size&&e.sha256===f.sha256)))throw Error('backup_changed_during_restore');
          const originalIdentity=await this._identity(destination);
          journal.stores.push({store,index,hadPrevious:originalIdentity!==null,originalIdentity,incomingIdentity:await this._identity(incoming),step:'planned'});
          await this._writeJournal(transaction,journal);
        }
        journal.phase='prepared';await this._writeJournal(transaction,journal);
        // The caller durably records its renderer notes recovery before live data moves.
        if(onPrepared)await onPrepared({rollbackPath:transaction});
        journal.phase='applying';await this._writeJournal(transaction,journal);
        for(const item of journal.stores) {
          const op=await this._operation(transaction,item);
          if(await this._identity(op.destination)!==item.originalIdentity)throw Error('live_store_changed_during_restore');
          if(item.hadPrevious){item.step='moving_previous';await this._writeJournal(transaction,journal);await assertPlain(op.destination);await fs.rename(op.destination,op.previous);item.step='previous_moved';await this._writeJournal(transaction,journal);}
          item.step='installing';await this._writeJournal(transaction,journal);
          await fs.mkdir(path.dirname(op.destination),{recursive:true});await assertPlain(op.destination);await fs.rename(op.incoming,op.destination);
          item.step='installed';await this._writeJournal(transaction,journal);
        }
        journal.phase='applied';await this._writeJournal(transaction,journal);
        await atomicWrite(path.join(this.root,'restore-state.json'),JSON.stringify({schemaVersion:manifest.schemaVersion,restoredAt:new Date().toISOString(),rollbackPath:transaction,phase:'pending_commit'}));
        return {restored:true,stores:manifest.stores,rollbackPath:transaction,restartRequired:true,...(notesSnapshot!==undefined?{notesSnapshot}:{})};
      }catch(error){
        try{await this._rollbackTransaction(transaction,{allowCommitted:false});}
        catch(recoveryError){const failure=Error('restore_rollback_incomplete');failure.recoveryPath=transaction;failure.cause=recoveryError;throw failure;}
        error.recoveryPath=transaction;throw error;
      }
    });
  }
  async _rollbackTransaction(rollbackPath,{allowCommitted=false}={}) {
    const {transaction,journal}=await this._transaction(rollbackPath);
    if(journal.phase==='rolled_back')return {rolledBack:true,alreadyRolledBack:true,rollbackPath:transaction,restartRequired:true};
    if(journal.phase==='committed'&&!allowCommitted)return {skipped:true,rollbackPath:transaction};
    if(journal.phase==='staging'){
      // Staging never touches a live store; inconsistent layouts require manual diagnosis.
      for(const item of journal.stores){const op=await this._operation(transaction,item);if(await this._exists(op.previous)||await this._exists(op.replaced)||await this._identity(op.destination)!==item.originalIdentity)throw Error('rollback_staging_state_ambiguous');}
      // Retain partial copies for diagnosis.
      journal.phase='rolled_back';journal.recoveredAt=new Date().toISOString();await this._writeJournal(transaction,journal);
      return {rolledBack:true,rollbackPath:transaction,restartRequired:true};
    }
    const operations=[];
    // Validate every original before moving anything. Ambiguous state preserves all bytes.
    for(const item of journal.stores){
      const op=await this._operation(transaction,item);
      const previous=await this._identity(op.previous);const current=await this._identity(op.destination);const replaced=await this._exists(op.replaced);
      if(item.hadPrevious){
        if(previous!==null&&previous!==item.originalIdentity)throw Error('rollback_original_corrupt');
        if(previous===null&&current!==item.originalIdentity)throw Error('rollback_original_missing');
        if(previous!==null&&current!==null&&replaced)throw Error('rollback_replacement_ambiguous');
      }else{
        if(previous!==null)throw Error('rollback_unexpected_original');
        if(current!==null&&replaced)throw Error('rollback_replacement_ambiguous');
      }
      operations.push(op);
    }
    journal.phase='rolling_back';await this._writeJournal(transaction,journal);
    for(const op of operations.reverse()){
      const item=journal.stores.find(item=>item.index===op.index);
      if(await this._exists(op.previous)){
        if(await this._exists(op.destination)){item.rollbackStep='preserving_replacement';await this._writeJournal(transaction,journal);await fs.rename(op.destination,op.replaced);}
        item.rollbackStep='restoring_original';await this._writeJournal(transaction,journal);await fs.rename(op.previous,op.destination);
      }else if(!item.hadPrevious&&await this._exists(op.destination)){
        item.rollbackStep='preserving_replacement';await this._writeJournal(transaction,journal);await fs.rename(op.destination,op.replaced);
      }
      item.rollbackStep='restored';await this._writeJournal(transaction,journal);
    }
    journal.phase='rolled_back';journal.recoveredAt=new Date().toISOString();await this._writeJournal(transaction,journal);
    return {rolledBack:true,rollbackPath:transaction,restartRequired:true};
  }
  async rollbackRestore({rollbackPath}) {
    return this._exclusive(()=>this._rollbackTransaction(rollbackPath,{allowCommitted:true}));
  }
  async commitRestore({rollbackPath}) {
    // Metadata-only: services are already running when the caller commits.
    if(this.busy)throw Error('data_operation_running');this.busy=true;
    try{
      const {transaction,journal}=await this._transaction(rollbackPath);
      if(journal.phase==='committed')return {committed:true,alreadyCommitted:true,rollbackPath:transaction};
      if(journal.phase!=='applied')throw Error('restore_not_ready_to_commit');
      journal.phase='committed';journal.committedAt=new Date().toISOString();await this._writeJournal(transaction,journal);
      return {committed:true,rollbackPath:transaction};
    }finally{this.busy=false;}
  }
  async recoverInterruptedRestores() {
    return this._exclusive(async()=>{
      const backups=await safePath(this.root,'backups');const result={recovered:[],committed:[],alreadyRolledBack:[]};
      if(!await this._exists(backups))return result;
      const names=(await fs.readdir(backups,{withFileTypes:true})).filter(entry=>/^restore-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(entry.name));
      const pending=[];
      for(const entry of names){
        const rollbackPath=path.join(backups,entry.name);
        try{
          await assertPlain(rollbackPath);
          if(!entry.isDirectory()||entry.isSymbolicLink())throw Error('invalid_rollback_directory');
          const {journal}=await this._transaction(rollbackPath);
          if(journal.phase==='committed'){result.committed.push({rollbackPath});continue;}
          if(journal.phase==='rolled_back'){result.alreadyRolledBack.push({rollbackPath});continue;}
          pending.push({rollbackPath,createdAt:journal.createdAt||''});
        }catch(error){const failure=Error('restore_recovery_required');failure.recoveryPath=rollbackPath;failure.reason=error.code||error.message;throw failure;}
      }
      // A newer pending transaction must be reversed before an older one.
      pending.sort((a,b)=>b.createdAt.localeCompare(a.createdAt));
      for(const item of pending)try{result.recovered.push(await this._rollbackTransaction(item.rollbackPath));}
      catch(error){const failure=Error('restore_recovery_required');failure.recoveryPath=item.rollbackPath;failure.reason=error.code||error.message;throw failure;}
      return result;
    });
  }
  async cleanupCache() {
    return this._exclusive(async()=>{
      // Only generated cache content is eligible, never uploads/models/database/history.
      const target=await safePath(this.root,'cache');const stat=await this._exists(target);if(!stat)return {filesRemoved:0};
      const files=await walk(target);for(const entry of await fs.readdir(target))await removeTree(await safePath(target,entry));
      return {filesRemoved:files.length};
    });
  }
  async diagnostics({destination,metadata={}}) {
    const target=this._external(destination);await assertPlain(target);if(await this._exists(target))throw Error('diagnostics_destination_exists');
    const report={format:'framewise-diagnostics',version:1,createdAt:new Date().toISOString(),metadata:pickSafe(metadata,METADATA_KEYS),events:[]};
    const logs=await safePath(this.root,'logs');
    if(await this._exists(logs))for(const entry of (await fs.readdir(logs,{withFileTypes:true})).filter(e=>e.isFile()&&/^[a-zA-Z0-9._-]+\.jsonl$/.test(e.name)).slice(0,10)) {
      const file=await safePath(logs,entry.name);const stat=await fs.stat(file);if(stat.size>4*1024*1024)continue;
      for(const line of (await fs.readFile(file,'utf8')).split('\n').slice(-500))try{const event=pickSafe(JSON.parse(line),EVENT_KEYS);if(Object.keys(event).length)report.events.push(event);}catch{}
    }
    await atomicWrite(target,JSON.stringify(report,null,2));return {path:target,events:report.events.length};
  }
  async migrate({source}) {return this.restore({source});}
  async recordUpgrade({appVersion,schemaVersion}) {
    return this._exclusive(async()=>{
      if(typeof appVersion!=='string'||!/^\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9.-]+)?$/.test(appVersion)||!Number.isSafeInteger(schemaVersion)||schemaVersion<1)throw Error('invalid_upgrade');
      const target=await safePath(this.root,'runtime-state.json');let previous=null;
      try{previous=JSON.parse(await fs.readFile(target,'utf8'));}catch(error){if(error.code!=='ENOENT')throw error;}
      if(previous&&schemaVersion<previous.schemaVersion)throw Error('schema_downgrade_requires_restore');
      const state={appVersion,schemaVersion,status:'pending',previous:previous?{appVersion:previous.appVersion,schemaVersion:previous.schemaVersion}:null,updatedAt:new Date().toISOString()};
      await atomicWrite(target,JSON.stringify(state,null,2));return state;
    });
  }
  async confirmUpgrade() {const target=await safePath(this.root,'runtime-state.json');const state=JSON.parse(await fs.readFile(target,'utf8'));state.status='ready';await atomicWrite(target,JSON.stringify(state,null,2));return state;}
}
module.exports={DataSupport,pickSafe,PROFILE_STORES,DATA_STORES};



