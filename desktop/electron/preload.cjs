const {contextBridge,ipcRenderer,webUtils}=require('electron');
contextBridge.exposeInMainWorld('framewiseMedia',{
 register:file=>ipcRenderer.invoke('media:register',webUtils.getPathForFile(file)),
 restore:fingerprint=>ipcRenderer.invoke('media:restore',fingerprint)
});

if(process.argv.includes('--framewise-native'))contextBridge.exposeInMainWorld('framewiseDesktop',Object.fromEntries(['status','saveSettings','start','restart','installModels','cancelModels','exportBackup','restoreBackup','exportDiagnostics','clearCache','openDataDirectory','importModels'].map(name=>[name,(value)=>ipcRenderer.invoke('native:'+name,value)])));

if(process.argv.includes('--framewise-native'))ipcRenderer.on('native:state',(_event,state)=>{if(state&&typeof state.phase==='string')window.dispatchEvent(new CustomEvent('framewise-runtime-state',{detail:{phase:state.phase,apiOrigin:state.apiOrigin}}))});
