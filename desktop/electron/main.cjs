const { app, BrowserWindow, Menu, protocol, net, session } = require('electron');
const path=require('node:path');const fs=require('node:fs');const {pathToFileURL}=require('node:url');
const {assetPath,allowedNavigation}=require('./assets.cjs');
app.setName('Framewise');app.setAppUserModelId('cn.framewise.desktop');
const profile=app.commandLine.getSwitchValue('user-data-dir');if(profile){fs.mkdirSync(profile,{recursive:true});app.setPath('userData',path.resolve(profile))}
protocol.registerSchemesAsPrivileged([{scheme:'app',privileges:{standard:true,secure:true,supportFetchAPI:true,corsEnabled:true,stream:true}}]);
const development=!app.isPackaged&&process.argv.includes('--dev');
let mainWindow;
if(!app.requestSingleInstanceLock())app.quit();
else {
 app.on('second-instance',()=>{if(mainWindow){if(mainWindow.isMinimized())mainWindow.restore();mainWindow.show();mainWindow.focus()}});
 function createWindow(){
  const window=new BrowserWindow({title:'Framewise',icon:path.join(__dirname,'../dist/framewise-512.png'),width:1440,height:940,minWidth:1024,minHeight:700,show:false,backgroundColor:'#f5f7ff',autoHideMenuBar:true,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true}});
  mainWindow=window;
  window.once('ready-to-show',()=>window.show());
  window.on('closed',()=>{if(mainWindow===window)mainWindow=null});
  window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  window.webContents.on('will-attach-webview',event=>event.preventDefault());
  window.webContents.on('will-navigate',(event,url)=>{if(!allowedNavigation(url,development))event.preventDefault()});
  window.webContents.on('page-title-updated',event=>{event.preventDefault();window.setTitle('Framewise')});
  void window.loadURL(development?'http://127.0.0.1:5173/':'app://framewise/index.html');
 }
 app.whenReady().then(()=>{
  const root=path.resolve(__dirname,'../dist');
  protocol.handle('app',async request=>{const file=assetPath(request.url,root);if(!file)return new Response('Not found',{status:404});try{return await net.fetch(pathToFileURL(file).toString())}catch{return new Response('Not found',{status:404})}});
  session.defaultSession.setPermissionRequestHandler((contents,permission,callback)=>callback(allowedNavigation(contents.getURL(),development)&&['fullscreen','clipboard-sanitized-write'].includes(permission)));
  Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'文件',submenu:[{role:'quit',label:'退出 Framewise'}]},{label:'编辑',submenu:[{role:'undo',label:'撤销'},{role:'redo',label:'重做'},{type:'separator'},{role:'cut',label:'剪切'},{role:'copy',label:'复制'},{role:'paste',label:'粘贴'},{role:'selectAll',label:'全选'}]},{label:'视图',submenu:[{role:'reload',label:'刷新'},{role:'resetZoom',label:'实际大小'},{role:'zoomIn',label:'放大'},{role:'zoomOut',label:'缩小'},{role:'togglefullscreen',label:'全屏'}]}]));
  createWindow();app.on('activate',()=>{if(BrowserWindow.getAllWindows().length===0)createWindow()});
 });
 app.on('window-all-closed',()=>{if(process.platform!=='darwin')app.quit()});
}
