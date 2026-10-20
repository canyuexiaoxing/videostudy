"use strict";
const fs=require('node:fs/promises');
const path=require('node:path');
const {assertPlain}=require('./storage-paths.cjs');
const SAFE_REASONS=new Set(['invalid_settings','settings_too_large','secure_storage_unavailable','invalid_device','invalid_deepseek','invalid_api_url','invalid_model','invalid_model_manifest','unsafe_path','EACCES','ENOSPC','EPERM']);
function initializationReason(error){if(error instanceof SyntaxError)return 'invalid_settings';const candidate=error?.code||error?.message;return SAFE_REASONS.has(candidate)?candidate:'initialization_failed';}
async function initializationAction({name,error,dataDir,version,window,dialog,shell}){
 const reason=initializationReason(error);
 if(name==='status')return {phase:'error',error:'runtime_initialization_failed',initializationReason:reason,settings:{mode:'auto',hasKey:false},models:{state:'absent'},paths:{dataDir}};
 if(name==='openDataDirectory'){await assertPlain(dataDir);await fs.mkdir(dataDir,{recursive:true});const result=await shell.openPath(dataDir);if(result)throw Error('data_directory_open_failed');return {ok:true};}
 if(name==='exportDiagnostics'){
  const selected=await dialog.showSaveDialog(window,{title:'导出初始化诊断',defaultPath:'Framewise-initialization-diagnostics.json',filters:[{name:'诊断文件',extensions:['json']}]});
  if(selected.canceled)return {cancelled:true};
  if(typeof selected.filePath!=='string'||!path.isAbsolute(selected.filePath))throw Error('invalid_diagnostics_path');
  await assertPlain(selected.filePath);
  const report={format:'framewise-initialization-diagnostics',version:1,createdAt:new Date().toISOString(),appVersion:version,platform:process.platform,arch:process.arch,error:'runtime_initialization_failed',reason,settingsPreserved:true};
  let handle;try{handle=await fs.open(selected.filePath,'wx',0o600);await handle.writeFile(JSON.stringify(report,null,2));await handle.sync();}catch(failure){if(failure.code==='EEXIST')throw Error('diagnostics_destination_exists');throw failure;}finally{await handle?.close();}
  return {ok:true};
 }
 return {ok:false,error:'runtime_initialization_failed'};
}
module.exports={initializationAction,initializationReason};
