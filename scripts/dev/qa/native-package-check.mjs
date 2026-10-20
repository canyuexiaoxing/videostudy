import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),require=createRequire(import.meta.url);
const asar=await import(pathToFileURL(path.join(root,'desktop/node_modules/@electron/asar/lib/asar.js')).href);
const latest=JSON.parse(await fs.readFile(path.join(root,'.local/releases/latest.json'),'utf8'));
const argument=process.argv.find(x=>x.startsWith('--folder='));
const folder=argument?path.resolve(argument.slice(9)):latest.folder;
const manifest=await require(path.join(root,'desktop/electron/native-runtime.cjs')).verifyRuntime(path.join(folder,'resources/runtime'));
const archive=path.join(folder,'resources/app.asar'),list=asar.listPackage(archive);
const expected=(await fs.readdir(path.join(root,'desktop/electron'))).filter(x=>x.endsWith('.cjs')&&!x.endsWith('.test.cjs'));
for(const file of expected){
 if(!list.some(x=>x.replaceAll('\\','/')==='/electron/'+file))throw Error('missing_electron_module:'+file);
 if(process.argv.includes('--current-source')&&!asar.extractFile(archive,'electron/'+file).equals(await fs.readFile(path.join(root,'desktop/electron',file))))throw Error('outdated_electron_module:'+file);
}
if(list.some(x=>x.includes('.test.cjs')||x.includes('framewise-preview')))throw Error('development_assets_packaged');
const result={stage:'native_package_verified',folder,criticalFiles:manifest.critical.length,electronModules:expected.length,version:JSON.parse(asar.extractFile(archive,'package.json').toString()).version};
await fs.writeFile(path.join(root,'.local/qa/native-delivery/package-verification.json'),JSON.stringify(result,null,2));
console.log(JSON.stringify(result));

