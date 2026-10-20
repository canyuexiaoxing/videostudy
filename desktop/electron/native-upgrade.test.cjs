"use strict";
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {execFile}=require('node:child_process'),{promisify}=require('node:util');const execute=promisify(execFile);
const {UpgradeGuard,compareVersions}=require('./native-upgrade.cjs');
const python=path.resolve(__dirname,'../../.local/native/runtime/python/python.exe');
async function fixture(t){const temp=await fs.mkdtemp(path.join(os.tmpdir(),'framewise-upgrade-'));t.after(async()=>{if(path.isAbsolute(temp)&&path.basename(temp).startsWith('framewise-upgrade-'))await fs.rm(temp,{recursive:true,force:true});});const dataDir=path.join(temp,'data'),oldExe=path.join(temp,'install/versions/0.2.0/Framewise.exe'),newExe=path.join(temp,'install/versions/0.3.0/Framewise.exe');await fs.mkdir(path.dirname(oldExe),{recursive:true});await fs.mkdir(path.dirname(newExe),{recursive:true});await fs.writeFile(oldExe,'old');await fs.writeFile(newExe,'new');const config={dataDir,version:'0.3.0',executable:newExe,python,ensureStopped:async()=>true};return {temp,dataDir,oldExe,newExe,config,guard:new UpgradeGuard(config),database:path.join(dataDir,'database/framewise.db'),state:path.join(dataDir,'runtime/package-state.json')};}
async function sql(file,script){await fs.mkdir(path.dirname(file),{recursive:true});return execute(python,['-I','-c',`import sqlite3,sys,json,os
c=sqlite3.connect(sys.argv[1])
${script}`,file],{windowsHide:true});}
async function ready(f){await new UpgradeGuard({...f.config,version:'0.2.0',executable:f.oldExe}).confirm();}
async function create(f,wal=false){await sql(f.database,`c.execute('PRAGMA journal_mode=WAL')
c.execute('PRAGMA wal_autocheckpoint=0')
c.execute('CREATE TABLE notes(id INTEGER PRIMARY KEY, value TEXT)')
c.execute("INSERT INTO notes(value) VALUES ('before')")
c.execute('PRAGMA user_version=19')
c.commit()
${wal?'os._exit(0)':'c.close()'}`);}
async function values(f){const {stdout}=await sql(f.database,`print(json.dumps({'values':c.execute('SELECT value FROM notes ORDER BY id').fetchall(),'schema':c.execute('PRAGMA user_version').fetchone()[0]}))
c.close()`);return JSON.parse(stdout);}

test('semantic versions reject actual downgrades including prerelease precedence',()=>{assert.equal(compareVersions('0.3.0','0.2.9'),1);assert.equal(compareVersions('1.0.0-rc.1','1.0.0'),-1);assert.equal(compareVersions('1.0.0-beta.2','1.0.0-beta.11'),-1);assert.equal(compareVersions('1.0.0+build','1.0.0'),0);assert.throws(()=>compareVersions('1.0.0-01','1.0.0'),/invalid_version/);});

test('first installation and same ready version do not create repeated backups',async t=>{const f=await fixture(t);assert.deepEqual(await f.guard.beforeStart(),{backup:false});await f.guard.confirm();await create(f);assert.deepEqual(await f.guard.beforeStart(),{backup:false});assert.equal((JSON.parse(await fs.readFile(f.state))).ready.version,'0.3.0');await assert.rejects(fs.access(path.join(f.dataDir,'backups')));});

test('real SQLite online backup captures WAL data, retries reuse snapshot, rollback restores database only',async t=>{const f=await fixture(t);await ready(f);await create(f,true);assert.ok((await fs.stat(f.database+'-wal')).size>0);for(const name of ['settings.json','models/model.bin','notes/keep.json']){const target=path.join(f.dataDir,name);await fs.mkdir(path.dirname(target),{recursive:true});await fs.writeFile(target,'keep');}
 let snapshots=0;f.guard=new UpgradeGuard({...f.config,run:async(...args)=>{snapshots++;return execute(...args);}});const before=await f.guard.beforeStart();assert.equal(before.backup,true);assert.equal((await f.guard.beforeStart()).reused,true);assert.equal(snapshots,1);assert.equal(await f.guard.previousExecutable(),f.oldExe);
 await sql(f.database,`c.execute("INSERT INTO notes(value) VALUES ('after')")
c.execute('PRAGMA user_version=20')
c.commit()
c.close()`);assert.equal((await values(f)).schema,20);
 assert.equal((await f.guard.rollback()).restored,true);assert.deepEqual(await values(f),{values:[['before']],schema:19});for(const name of ['settings.json','models/model.bin','notes/keep.json'])assert.equal(await fs.readFile(path.join(f.dataDir,name),'utf8'),'keep');const pending=JSON.parse(await fs.readFile(f.state)).pending;assert.ok(pending.rolledBackAt);assert.ok((await fs.readdir(path.join(f.dataDir,pending.backupRelative))).some(name=>name.startsWith('failed-')));
 await f.guard.beforeStart();assert.equal(JSON.parse(await fs.readFile(f.state)).pending.rolledBackAt,undefined);assert.equal(snapshots,1);await f.guard.confirm();assert.equal(JSON.parse(await fs.readFile(f.state)).pending,undefined);
});

test('corrupted snapshot is rejected before any database replacement',async t=>{const f=await fixture(t);await ready(f);await create(f);await f.guard.beforeStart();const pending=JSON.parse(await fs.readFile(f.state)).pending;await fs.appendFile(path.join(f.dataDir,pending.backupRelative,'framewise.db'),'corrupt');await assert.rejects(f.guard.rollback(),/upgrade_backup_invalid/);assert.deepEqual(await values(f),{values:[['before']],schema:19});});

test('active services block snapshots and rollback, confirm may mark a running healthy service ready',async t=>{const f=await fixture(t);const guard=new UpgradeGuard({...f.config,ensureStopped:async()=>false});await assert.rejects(guard.beforeStart(),/runtime_not_stopped/);await assert.rejects(guard.rollback(),/runtime_not_stopped/);await guard.confirm();assert.equal(JSON.parse(await fs.readFile(f.state)).ready.version,'0.3.0');});

test('newer ready data and unrolled pending migrations reject an older application',async t=>{const f=await fixture(t);await ready(f);await create(f);await f.guard.beforeStart();const old=new UpgradeGuard({...f.config,version:'0.2.0',executable:f.oldExe});await assert.rejects(old.beforeStart(),/upgrade_data_newer_than_app/);await f.guard.rollback();assert.deepEqual(await old.beforeStart(),{backup:false});await f.guard.confirm();await assert.rejects(old.beforeStart(),/upgrade_data_newer_than_app/);await assert.rejects(old.confirm(),/upgrade_data_newer_than_app/);});

test('pending traversal and foreign previous executable cannot escape owned roots',async t=>{const f=await fixture(t);await ready(f);await create(f);await f.guard.beforeStart();const state=JSON.parse(await fs.readFile(f.state));state.pending.previousExecutable=path.join(f.temp,'foreign/Framewise.exe');await fs.mkdir(path.dirname(state.pending.previousExecutable),{recursive:true});await fs.writeFile(state.pending.previousExecutable,'foreign');await fs.writeFile(f.state,JSON.stringify(state));assert.equal(await f.guard.previousExecutable(),null);state.pending.backupRelative='../outside';await fs.writeFile(f.state,JSON.stringify(state));await assert.rejects(f.guard.rollback(),/upgrade_invalid_state/);assert.deepEqual(await values(f),{values:[['before']],schema:19});});

test('symlink database directories and missing stop contracts are rejected',async t=>{const f=await fixture(t);const outside=path.join(f.temp,'outside');await fs.mkdir(outside);await fs.mkdir(f.dataDir,{recursive:true});await fs.symlink(outside,path.join(f.dataDir,'database'),'junction');await assert.rejects(f.guard.beforeStart(),/symlink_forbidden/);await assert.rejects(new UpgradeGuard({...f.config,ensureStopped:undefined}).beforeStart(),/runtime_not_stopped/);await fs.unlink(path.join(f.dataDir,'database'));});

test('subprocess failures expose safe code without Python source or database paths',async t=>{const f=await fixture(t);await ready(f);await create(f);const guard=new UpgradeGuard({...f.config,run:async()=>{throw Error('private SQL source /secret/path');}});await assert.rejects(guard.beforeStart(),error=>error.message==='upgrade_snapshot_failed');const state=JSON.parse(await fs.readFile(f.state));assert.equal(state.pending,undefined);const log=await fs.readFile(path.join(f.dataDir,'logs/native-upgrade.jsonl'),'utf8');assert.ok(!log.includes('private SQL'));});
