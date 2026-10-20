'use strict';
const fs=require('node:fs/promises'),path=require('node:path');
function installRuntimeNetwork(session,{getRuntime,getWindow,dataDir,write}){
 let chain=Promise.resolve(),size=0;const file=path.join(dataDir,'logs','desktop-network.jsonl');
 const save=write||((value)=>{chain=chain.then(async()=>{const line=JSON.stringify(value)+'\n';size+=Buffer.byteLength(line);if(size>1024*1024){await fs.rename(file,file+'.previous').catch(()=>{});size=0}await fs.appendFile(file,line)}).catch(()=>{})});
 function identity(details){try{const u=new URL(details.url);if(!['127.0.0.1','localhost','[::1]'].includes(u.hostname)||u.protocol!=='http:'||!/^\/api\/transcriptions(?:\/[0-9a-f-]{36})?$/.test(u.pathname))return null;return {origin:u.origin,path:u.pathname}}catch{return null}}
 function record(details,event,extra={}){const id=identity(details);if(!id)return;save({timestamp:new Date().toISOString(),event,...id,expectedOrigin:getRuntime()?.apiOrigin,windowMatches:details.webContentsId===getWindow()?.webContents.id,...extra})}
 session.webRequest.onBeforeSendHeaders((details,callback)=>{const runtime=getRuntime(),origin=runtime?.apiOrigin;for(const key of Object.keys(details.requestHeaders))if(key.toLowerCase()==='x-framewise-runtime')delete details.requestHeaders[key];const inject=!!origin&&details.webContentsId===getWindow()?.webContents.id&&details.url.startsWith(origin+'/')&&typeof runtime.token==='string';if(inject)details.requestHeaders['X-Framewise-Runtime']=runtime.token;record(details,'request',{method:details.method,headerInjected:inject,servicePhase:runtime?.phase});callback({requestHeaders:details.requestHeaders})});
 session.webRequest.onCompleted(details=>{const headers=details.responseHeaders||{},entry=Object.entries(headers).find(([k])=>k.toLowerCase()==='access-control-allow-origin'),allowed=entry?.[1];record(details,'response',{httpStatus:details.statusCode,corsAllowsDesktop:Array.isArray(allowed)&&allowed.includes('app://framewise')})});
 session.webRequest.onErrorOccurred(details=>{const match=String(details.error||'').match(/ERR_[A-Z_]+/);record(details,'network_error',{errorCode:match?match[0]:'network_failed'})});
}
module.exports={installRuntimeNetwork};
