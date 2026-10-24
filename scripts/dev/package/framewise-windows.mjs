import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {readFile,writeFile,mkdir,cp,stat,readdir} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),desktop=path.join(root,'desktop');
if(process.platform!=='win32')throw new Error('This command builds the local Windows x64 distribution.');
const started=Date.now(),skipArchive=process.argv.includes('--skip-archive');
const pkg=JSON.parse(await readFile(path.join(desktop,'package.json'),'utf8'));const electron=JSON.parse(await readFile(path.join(desktop,'node_modules/electron/package.json'),'utf8'));
const runtime=path.join(root,'.local/native/runtime');
const {createRequire}=await import('node:module');const require=createRequire(import.meta.url);
await require(path.join(desktop,'electron/native-runtime.cjs')).verifyRuntime(runtime);
const stamp=new Date().toISOString().replace(/[:.]/g,'-'),stage=path.join(root,'.local/dev/framewise-package',stamp),out=process.argv.find(v=>v.startsWith('--output-dir='))?.slice(13)||path.join(root,'.local/releases',stamp);
await mkdir(stage,{recursive:true});await mkdir(out,{recursive:true});
await cp(path.join(desktop,'dist'),path.join(stage,'dist'),{recursive:true,filter:source=>!source.split(path.sep).includes('framewise-preview')});
await mkdir(path.join(stage,'electron'));for(const file of await readdir(path.join(desktop,'electron')))if(file.endsWith('.cjs')&&!file.endsWith('.test.cjs'))await cp(path.join(desktop,'electron',file),path.join(stage,'electron',file));
await writeFile(path.join(stage,'package.json'),JSON.stringify({name:'framewise',productName:'Framewise',author:'Framewise',license:'UNLICENSED',version:pkg.version,main:'electron/main.cjs',description:pkg.description,private:true},null,2));
const {packager}=await import(pathToFileURL(path.join(desktop,'node_modules/@electron/packager/dist/index.js')).href);
const cache=path.join(root,'.local/dev/electron-cache');const zip=path.join(cache,`electron-v${electron.version}-win32-x64.zip`);let localZip=false;try{localZip=(await stat(zip)).isFile()}catch{}
const apps=await packager({dir:stage,name:'Framewise',executableName:'Framewise',platform:'win32',arch:'x64',electronVersion:electron.version,appVersion:pkg.version,asar:true,prune:false,out,icon:path.join(desktop,'public/favicon.ico'),win32metadata:{ProductName:'Framewise',FileDescription:'Framewise classroom learning workspace'},...(localZip?{electronZipDir:cache}:{})});
const folder=apps[0];
console.log(JSON.stringify({stage:'copy_native_runtime',folder}));
await cp(runtime,path.join(folder,'resources/runtime'),{recursive:true,filter:source=>!source.split(path.sep).includes('__pycache__')&&!source.endsWith('.pyc')});
await writeFile(path.join(folder,'使用说明.txt'),'Framewise '+pkg.version+' Windows 桌面版\r\n\r\n双击 Framewise.exe，无需 Docker、Java、Python 或 FFmpeg 开发环境。请保留整个目录，不能单独移动 exe。\r\n首次进入设置配置个人 DeepSeek API Key，并准备模型；默认优先 GPU，不可用时自动使用 CPU。只有 GPU 模式遇到不兼容设备会明确提示。\r\n数据库、笔记、缓存、模型与加密密钥保存在当前用户应用数据目录；设置中可打开目录、备份、恢复和导出脱敏诊断。卸载保留这些数据。原视频仍留在用户选择的位置。\r\n安装包如包含 .bin 分卷，必须与 Setup.exe 一起保留。升级前建议导出备份。此构建未数字签名；第三方许可资料见 resources/runtime/licenses 和模型声明；外部分发前需完成对应许可证审核。\r\n');
let archive=null;
if(!skipArchive){archive=path.join(out,`Framewise-${pkg.version}-windows-x64.zip`);const quote=value=>"'"+value.replaceAll("'","''")+"'";execFileSync('powershell.exe',['-NoProfile','-Command',`$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::CreateFromDirectory(${quote(folder)},${quote(archive)},[System.IO.Compression.CompressionLevel]::Fastest,$true)`],{stdio:'inherit',windowsHide:true});}
const result={folder,exe:path.join(folder,'Framewise.exe'),archive,version:pkg.version,electron:electron.version,native:true,elapsedSeconds:Math.round((Date.now()-started)/1000)};
if(!process.argv.includes('--no-update-latest'))await writeFile(path.join(root,'.local/releases/latest.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
