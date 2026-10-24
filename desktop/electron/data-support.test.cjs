'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs/promises');const os=require('node:os');const path=require('node:path');const {LocalStorage}=require('./local-storage.cjs');const {DataSupport}=require('./data-support.cjs');
const notes={format:'framewise-renderer',version:1,notes:[{id:'note-1',scope:'course-1',timeMs:12,text:'private notes',createdAt:'2026-01-01',image:{type:'image/png',base64:'cGljdHVyZQ=='}}],localStorage:{'studyNotes:v1':'[]'}};
async function fixture(t,options={}){const base=await fs.mkdtemp(path.join(os.tmpdir(),'framewise-backup-'));t.after(()=>fs.rm(base,{recursive:true,force:true}));const profile=path.join(base,'profile');const storage=new LocalStorage({root:path.join(profile,'data')});await storage.init();const support=new DataSupport({storage,profileRoot:profile,ensureStopped:async()=>true,...options});await fs.writeFile(path.join(storage.paths.database,'app.sqlite3'),'original database');return {base,profile,storage,support,destination:path.join(base,'backup')};}
test('backup preserves database, all notes images and media paths but excludes credentials and video originals',async t=>{const {profile,storage,support,destination}=await fixture(t);await fs.mkdir(path.join(profile,'Local Storage'));await fs.writeFile(path.join(profile,'Local Storage','live-leveldb'),'not safe to copy live');await fs.writeFile(path.join(profile,'media-library.json'),'{}');await fs.writeFile(path.join(storage.root,'settings.json'),'encrypted-private-key');await fs.writeFile(path.join(storage.paths.uploads,'source.mp4'),'video');await fs.writeFile(path.join(storage.paths.models,'weights.bin'),'model');await support.backup({destination,notesSnapshot:notes});const manifest=JSON.parse(await fs.readFile(path.join(destination,'manifest.json'),'utf8'));assert.ok(manifest.files.some(f=>f.path==='app-notes.json'));assert.ok(manifest.files.some(f=>f.path==='profile/media-library.json'));assert.ok(manifest.files.every(f=>!/(settings|uploads|models|Local Storage)/.test(f.path)));await fs.writeFile(path.join(storage.paths.database,'app.sqlite3'),'new current database');const result=await support.restore({source:destination});assert.deepEqual(result.notesSnapshot,notes);assert.equal(await fs.readFile(path.join(storage.paths.database,'app.sqlite3'),'utf8'),'original database');assert.equal(await fs.readFile(path.join(storage.root,'settings.json'),'utf8'),'encrypted-private-key');await support.rollbackRestore({rollbackPath:result.rollbackPath});assert.equal(await fs.readFile(path.join(storage.paths.database,'app.sqlite3'),'utf8'),'new current database');});
test('runtime must explicitly be stopped and active notes require snapshot',async t=>{const {support,destination}=await fixture(t,{ensureStopped:async()=>false});await assert.rejects(support.backup({destination,notesSnapshot:notes}),/runtime_not_stopped/);const other=await fixture(t);await assert.rejects(other.support.backup({destination:other.destination}),/notes_snapshot_required/);await assert.rejects(fs.stat(other.destination),{code:'ENOENT'});});
test('corrupt, injected and traversal backup files cannot alter live data',async t=>{const {storage,support,destination}=await fixture(t);await support.backup({destination,notesSnapshot:notes});await fs.writeFile(path.join(destination,'data/database/app.sqlite3'),'tampered');await assert.rejects(support.restore({source:destination}),/backup_checksum_mismatch/);assert.equal(await fs.readFile(path.join(storage.paths.database,'app.sqlite3'),'utf8'),'original database');const file=path.join(destination,'manifest.json');const manifest=JSON.parse(await fs.readFile(file,'utf8'));manifest.files[0].path='../escape';await fs.writeFile(file,JSON.stringify(manifest));await assert.rejects(support.restore({source:destination}),/unsafe_path/);});
test('failed store promotion rolls back earlier changes',async t=>{const {storage,support,destination}=await fixture(t);await support.backup({destination,notesSnapshot:notes});await fs.writeFile(path.join(storage.paths.database,'app.sqlite3'),'current database');const rename=fs.rename;let failed=false;fs.rename=async(from,to)=>{if(!failed&&/incoming-1$/.test(from)){failed=true;throw Error('simulated_disk_error');}return rename(from,to);};try{await assert.rejects(support.restore({source:destination}),/simulated_disk_error/);}finally{fs.rename=rename;}assert.equal(await fs.readFile(path.join(storage.paths.database,'app.sqlite3'),'utf8'),'current database');});
test('cache cleanup never removes database, models, source files or notes',async t=>{const {storage,support}=await fixture(t);await fs.writeFile(path.join(storage.paths.cache,'derived.jpg'),'cached');await fs.writeFile(path.join(storage.paths.models,'model.bin'),'model');await fs.writeFile(path.join(storage.paths.uploads,'source.mp4'),'video');assert.equal((await support.cleanupCache()).filesRemoved,1);assert.equal(await fs.readFile(path.join(storage.paths.models,'model.bin'),'utf8'),'model');assert.equal(await fs.readFile(path.join(storage.paths.uploads,'source.mp4'),'utf8'),'video');assert.equal(await fs.readFile(path.join(storage.paths.database,'app.sqlite3'),'utf8'),'original database');});
test('junction in cache is refused before delete',async t=>{const {base,storage,support}=await fixture(t);const outside=path.join(base,'outside');await fs.mkdir(outside);await fs.writeFile(path.join(outside,'keep'),'keep');try{await fs.symlink(outside,path.join(storage.paths.cache,'junction'),'junction');}catch(error){if(error.code==='EPERM'){t.skip('junction creation unavailable');return;}throw error;}await assert.rejects(support.cleanupCache(),/symlink_forbidden/);assert.equal(await fs.readFile(path.join(outside,'keep'),'utf8'),'keep');await fs.unlink(path.join(storage.paths.cache,'junction'));});
test('diagnostics export only allowed fields and reject secret-looking scalar values',async t=>{const {base,storage,support}=await fixture(t);await fs.writeFile(path.join(storage.paths.logs,'events.jsonl'),JSON.stringify({event:'analysis_complete',stage:'asr',status:'ready',durationMs:34,apiKey:'sk-topsecret',body:'course text',request:'raw request',errorType:'Bearer secret',taskId:'sk-sensitive',requestId:'req_123'})+'\n');const target=path.join(base,'diagnostics.json');await support.diagnostics({destination:target,metadata:{appVersion:'0.3.0',platform:'win32',apiKey:'private',path:'C:/private',body:'course body'}});const text=await fs.readFile(target,'utf8');assert.doesNotMatch(text,/topsecret|sensitive|Bearer|course text|raw request|private|course body/);assert.match(text,/analysis_complete/);assert.match(text,/req_123/);});
test('schema markers forbid downgrade and record recoverable prior version',async t=>{const {support}=await fixture(t);await support.recordUpgrade({appVersion:'0.3.0',schemaVersion:1});await support.confirmUpgrade();const next=await support.recordUpgrade({appVersion:'0.4.0',schemaVersion:2});assert.equal(next.previous.appVersion,'0.3.0');await assert.rejects(support.recordUpgrade({appVersion:'0.3.0',schemaVersion:1}),/schema_downgrade_requires_restore/);});

// Construct interrupted filesystem states directly: recovery must work without a catch block.
async function interrupted(t,{phase='applying',step='planned',hadPrevious=true,position='before',missingOriginal=false,corruptOriginal=false}={}){
 const value=await fixture(t);const {storage,support}=value;
 const transaction=path.join(storage.paths.backups,'restore-11111111-2222-4333-8444-555555555555');await fs.mkdir(transaction);
 const live=storage.paths.database,incoming=path.join(transaction,'incoming-0'),previous=path.join(transaction,'previous-0'),replaced=path.join(transaction,'replaced-0');
 if(!hadPrevious)await fs.rm(live,{recursive:true});
 const originalIdentity=hadPrevious?await support._identity(live):null;
 await fs.mkdir(incoming);await fs.writeFile(path.join(incoming,'app.sqlite3'),'incoming database');
 const incomingIdentity=await support._identity(incoming);
 const journal={format:'framewise-restore-rollback',version:2,phase,createdAt:'2026-10-19T10:00:00.000Z',stores:[{store:'data/database',index:0,hadPrevious,originalIdentity,incomingIdentity,step}]};
 await support._writeJournal(transaction,journal);
 if(position==='previous_moved'||position==='installed'||position==='replacement_preserved'||position==='original_restored'){
   if(hadPrevious)await fs.rename(live,previous);
 }
 if(position==='installed'||position==='replacement_preserved'||position==='original_restored')await fs.rename(incoming,live);
 if(position==='replacement_preserved'||position==='original_restored')await fs.rename(live,replaced);
 if(position==='original_restored'&&hadPrevious)await fs.rename(previous,live);
 if(missingOriginal&&hadPrevious)await fs.rm(previous,{recursive:true,force:true});
 if(corruptOriginal&&hadPrevious)await fs.writeFile(path.join(previous,'app.sqlite3'),'corrupt original');
 return {...value,transaction,live,incoming,previous,replaced,journal};
}
test('prepared callback sees durable full plan before any original store moves',async t=>{
 const {storage,support,destination}=await fixture(t);await support.backup({destination,notesSnapshot:notes});
 await fs.writeFile(path.join(storage.paths.database,'app.sqlite3'),'current before callback');let prepared=false;
 const result=await support.restore({source:destination,onPrepared:async({rollbackPath})=>{
   const journal=JSON.parse(await fs.readFile(path.join(rollbackPath,'transaction.json'),'utf8'));
   assert.equal(journal.version,2);assert.equal(journal.phase,'prepared');assert.equal(journal.stores[0].hadPrevious,true);assert.match(journal.stores[0].originalIdentity,/^[a-f0-9]{64}$/);
   assert.equal(await fs.readFile(path.join(storage.paths.database,'app.sqlite3'),'utf8'),'current before callback');
   await fs.writeFile(path.join(rollbackPath,'notes-before.json'),JSON.stringify(notes));prepared=true;
 }});
 assert.equal(prepared,true);assert.equal(JSON.parse(await fs.readFile(path.join(result.rollbackPath,'transaction.json'),'utf8')).phase,'applied');
 assert.ok(await fs.stat(path.join(result.rollbackPath,'notes-before.json')));
});
test('hard crashes before and after every forward rename recover original database idempotently',async t=>{
 for(const state of [
   {phase:'prepared',step:'planned',position:'before'},
   {step:'moving_previous',position:'before'},
   {step:'moving_previous',position:'previous_moved'},
   {step:'previous_moved',position:'previous_moved'},
   {step:'installing',position:'previous_moved'},
   {step:'installing',position:'installed'},
   {step:'installed',position:'installed'},
   {phase:'applied',step:'installed',position:'installed'},
 ]){
   const value=await interrupted(t,state);const recovered=await value.support.recoverInterruptedRestores();assert.equal(recovered.recovered.length,1,JSON.stringify(state));
   assert.equal(await fs.readFile(path.join(value.live,'app.sqlite3'),'utf8'),'original database');
   const again=await value.support.recoverInterruptedRestores();assert.equal(again.recovered.length,0);assert.equal(again.alreadyRolledBack.length,1);
   if(state.position==='installed')assert.equal(await fs.readFile(path.join(value.replaced,'app.sqlite3'),'utf8'),'incoming database');
 }
});
test('hard crash during rollback resumes safely on both sides of original rename',async t=>{
 for(const position of ['installed','replacement_preserved','original_restored']){
   const value=await interrupted(t,{phase:'rolling_back',step:'installed',position});await value.support.recoverInterruptedRestores();
   assert.equal(await fs.readFile(path.join(value.live,'app.sqlite3'),'utf8'),'original database');
   assert.equal(await fs.readFile(path.join(value.replaced,'app.sqlite3'),'utf8'),'incoming database');
 }
});
test('originally absent stores recover to absence without deleting incoming bytes',async t=>{
 for(const position of ['before','installed','replacement_preserved']){
   const value=await interrupted(t,{hadPrevious:false,step:'installing',position});await value.support.recoverInterruptedRestores();
   await assert.rejects(fs.stat(value.live),{code:'ENOENT'});
   const preserved=position==='before'?value.incoming:value.replaced;assert.equal(await fs.readFile(path.join(preserved,'app.sqlite3'),'utf8'),'incoming database');
 }
});
test('commit happens after service start without stopping it; startup skips committed history',async t=>{
 const value=await interrupted(t,{phase:'applied',step:'installed',position:'installed'});
 let stoppedCalls=0;value.support.ensureStopped=async()=>{stoppedCalls++;return false;};
 await value.support.commitRestore({rollbackPath:value.transaction});assert.equal(stoppedCalls,0);
 value.support.ensureStopped=async()=>true;const recovery=await value.support.recoverInterruptedRestores();assert.equal(recovery.committed.length,1);assert.equal(recovery.recovered.length,0);
 assert.equal(await fs.readFile(path.join(value.live,'app.sqlite3'),'utf8'),'incoming database');
 await value.support.rollbackRestore({rollbackPath:value.transaction});assert.equal(await fs.readFile(path.join(value.live,'app.sqlite3'),'utf8'),'original database');
});
test('missing or corrupt originals fail closed and preserve replacement database',async t=>{
 for(const failure of [{missingOriginal:true},{corruptOriginal:true}]){
   const value=await interrupted(t,{step:'installed',position:'installed',...failure});
   await assert.rejects(value.support.recoverInterruptedRestores(),error=>error.message==='restore_recovery_required'&&error.recoveryPath===value.transaction&&/rollback_original_(missing|corrupt)/.test(error.reason));
   assert.equal(await fs.readFile(path.join(value.live,'app.sqlite3'),'utf8'),'incoming database');
 }
});
test('missing journals are diagnosed while unrelated backup directories remain untouched',async t=>{
 const {storage,support}=await fixture(t);const unrelated=path.join(storage.paths.backups,'user-selected-backup');await fs.mkdir(unrelated);await fs.writeFile(path.join(unrelated,'keep'),'keep');
 assert.equal((await support.recoverInterruptedRestores()).recovered.length,0);
 const own=path.join(storage.paths.backups,'restore-aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee');await fs.mkdir(own);await fs.writeFile(path.join(own,'unrecognized-data'),'preserve');
 await assert.rejects(support.recoverInterruptedRestores(),error=>error.message==='restore_recovery_required'&&error.recoveryPath===own);
 assert.equal(await fs.readFile(path.join(own,'unrecognized-data'),'utf8'),'preserve');assert.equal(await fs.readFile(path.join(unrelated,'keep'),'utf8'),'keep');
});
test('crashed staging transactions never move original stores or delete partial copies',async t=>{
 const value=await interrupted(t,{phase:'staging'});await value.support.recoverInterruptedRestores();
 assert.equal(await fs.readFile(path.join(value.live,'app.sqlite3'),'utf8'),'original database');assert.equal(await fs.readFile(path.join(value.incoming,'app.sqlite3'),'utf8'),'incoming database');
});
test('a new restore cannot supersede an unresolved pending data generation',async t=>{
 const value=await interrupted(t,{phase:'applied',step:'installed',position:'installed'});
 await value.support.backup({destination:value.destination,notesSnapshot:notes});
 await assert.rejects(value.support.restore({source:value.destination}),error=>error.message==='pending_restore_requires_recovery'&&error.recoveryPath===value.transaction);
 assert.equal(await fs.readFile(path.join(value.live,'app.sqlite3'),'utf8'),'incoming database');
});
test('inconsistent staging layout fails closed rather than declaring recovery complete',async t=>{
 const value=await interrupted(t,{phase:'staging',position:'previous_moved'});
 await assert.rejects(value.support.recoverInterruptedRestores(),error=>error.message==='restore_recovery_required'&&error.reason==='rollback_staging_state_ambiguous');
 assert.equal(await fs.readFile(path.join(value.previous,'app.sqlite3'),'utf8'),'original database');
});

test('private model failure artifacts are excluded from diagnostics and course backups',async t=>{const {base,storage,support,destination}=await fixture(t);const privateDir=path.join(storage.paths.logs,'private-model-failures');await fs.mkdir(privateDir);await fs.writeFile(path.join(privateDir,'failure.json'),JSON.stringify({response:'PRIVATE_MODEL_RESPONSE',task:'course-id'}));const report=path.join(base,'diagnostics.json');await support.diagnostics({destination:report});assert.doesNotMatch(await fs.readFile(report,'utf8'),/PRIVATE_MODEL_RESPONSE|course-id/);await support.backup({destination,notesSnapshot:notes});const manifest=JSON.parse(await fs.readFile(path.join(destination,'manifest.json'),'utf8'));assert.ok(manifest.files.every(f=>!f.path.includes('private-model-failures')));assert.match(await fs.readFile(path.join(privateDir,'failure.json'),'utf8'),/PRIVATE_MODEL_RESPONSE/);});
