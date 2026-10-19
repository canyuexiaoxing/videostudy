const {contextBridge,ipcRenderer,webUtils}=require('electron');
contextBridge.exposeInMainWorld('framewiseMedia',{
 register:file=>ipcRenderer.invoke('media:register',webUtils.getPathForFile(file)),
 restore:fingerprint=>ipcRenderer.invoke('media:restore',fingerprint)
});
