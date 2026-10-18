import path from 'node:path';import {fileURLToPath,pathToFileURL} from 'node:url';import {readFile,writeFile,mkdir,cp,stat} from 'node:fs/promises';import {execFileSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),desktop=path.join(root,'desktop');
if(process.platform!=='win32')throw new Error('This command builds the local Windows x64 distribution.');
const pkg=JSON.parse(await readFile(path.join(desktop,'package.json'),'utf8'));const electron=JSON.parse(await readFile(path.join(desktop,'node_modules/electron/package.json'),'utf8'));
const stamp=new Date().toISOString().replace(/[:.]/g,'-'),stage=path.join(root,'.local/dev/framewise-package',stamp),out=path.join(root,'.local/releases',stamp);
await mkdir(stage,{recursive:true});await mkdir(out,{recursive:true});
await cp(path.join(desktop,'dist'),path.join(stage,'dist'),{recursive:true,filter:source=>!source.split(path.sep).includes('framewise-preview')});
await mkdir(path.join(stage,'electron'));for(const file of ['main.cjs','assets.cjs'])await cp(path.join(desktop,'electron',file),path.join(stage,'electron',file));
await writeFile(path.join(stage,'package.json'),JSON.stringify({name:'framewise',productName:'Framewise',author:'Framewise',license:'UNLICENSED',version:pkg.version,main:'electron/main.cjs',description:pkg.description,private:true},null,2));
const {packager}=await import(pathToFileURL(path.join(desktop,'node_modules/@electron/packager/dist/index.js')).href);
const cache=path.join(root,'.local/dev/electron-cache');const zip=path.join(cache,`electron-v${electron.version}-win32-x64.zip`);let localZip=false;try{localZip=(await stat(zip)).isFile()}catch{}
const apps=await packager({dir:stage,name:'Framewise',executableName:'Framewise',platform:'win32',arch:'x64',electronVersion:electron.version,appVersion:pkg.version,asar:true,prune:false,out,icon:path.join(desktop,'public/favicon.ico'),win32metadata:{ProductName:'Framewise',FileDescription:'Framewise classroom learning workspace'},...(localZip?{electronZipDir:cache}:{})});
const folder=apps[0];await writeFile(path.join(folder,'使用说明.txt'),'Framewise Windows 桌面版\r\n\r\n双击 Framewise.exe 启动，无需启动 Vite 或打开浏览器。请保留整个文件夹，不能只移动 exe。\r\n\r\n当前版本连接本机 http://127.0.0.1:18080 的分析服务；请保持现有 VideoStudy 后端服务运行。此包未内置 MySQL、Python/GPU模型及后端服务。\r\n\r\n视频本地播放；历史任务从现有后端读取。桌面版的历史关联、笔记和缩略图缓存保存在 Framewise 的独立用户数据中，与网页版分开。\r\n');
const archive=path.join(out,`Framewise-${pkg.version}-windows-x64.zip`);const quote=value=>"'"+value.replaceAll("'","''")+"'";
execFileSync('powershell.exe',['-NoProfile','-Command',`$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::CreateFromDirectory(${quote(folder)},${quote(archive)},[System.IO.Compression.CompressionLevel]::Fastest,$true)`],{stdio:'inherit',windowsHide:true});
const result={folder,exe:path.join(folder,'Framewise.exe'),archive,version:pkg.version,electron:electron.version};await writeFile(path.join(root,'.local/releases/latest.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
