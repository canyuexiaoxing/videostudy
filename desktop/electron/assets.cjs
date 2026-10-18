const path=require('node:path');
const TYPES=new Set(['.html','.js','.css','.svg','.png','.ico','.woff','.woff2','.ttf','.wasm']);
function assetPath(value,root){
 try{const url=new URL(value);if(url.protocol!=='app:'||url.hostname!=='framewise'||url.port||url.username||url.password)return null;
 const name=decodeURIComponent(url.pathname);if(name.includes('\\')||name.includes('\0')||name.split('/').some(s=>s.startsWith('.')))return null;
 const resolved=path.resolve(root,'.'+(name==='/'?'/index.html':name)),relative=path.relative(root,resolved);
 if(relative.startsWith('..')||path.isAbsolute(relative)||!TYPES.has(path.extname(resolved).toLowerCase()))return null;
 return resolved;
 }catch{return null}
}
function allowedNavigation(value,dev){try{const u=new URL(value);return u.origin==='http://127.0.0.1:5173'&&dev||u.protocol==='app:'&&u.hostname==='framewise'&&!u.port&&!u.username&&!u.password}catch{return false}}
module.exports={assetPath,allowedNavigation};
