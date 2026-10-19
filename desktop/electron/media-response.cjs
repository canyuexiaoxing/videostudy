const fs=require('node:fs');const {stat}=require('node:fs/promises');const {Readable}=require('node:stream');const path=require('node:path');
async function mediaResponse(request,file){
 const {size}=await stat(file);const types={'.webm':'video/webm','.mp4':'video/mp4','.m4v':'video/mp4','.mov':'video/quicktime','.mp3':'audio/mpeg','.wav':'audio/wav','.m4a':'audio/mp4','.ogg':'audio/ogg'};
 const headers={'Content-Type':types[path.extname(file).toLowerCase()]||'application/octet-stream','Accept-Ranges':'bytes','Cache-Control':'no-store'};
 const origin=request.headers.get('Origin');if(['http://127.0.0.1:5173','app://framewise'].includes(origin))headers['Access-Control-Allow-Origin']=origin;
 const range=request.headers.get('Range');let start=0,end=size-1,status=200;
 if(range){const match=/^bytes=(\d*)-(\d*)$/.exec(range);if(!match||(!match[1]&&!match[2]))return new Response(null,{status:416,headers:{...headers,'Content-Range':`bytes */${size}`}});
  start=match[1]?Number(match[1]):Math.max(0,size-Number(match[2]));end=match[1]&&match[2]?Math.min(Number(match[2]),size-1):size-1;
  if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<0||start>=size||end<start)return new Response(null,{status:416,headers:{...headers,'Content-Range':`bytes */${size}`}});
  status=206;headers['Content-Range']=`bytes ${start}-${end}/${size}`;
 }
 headers['Content-Length']=String(Math.max(0,end-start+1));
 if(request.method==='HEAD'||size===0)return new Response(null,{status,headers});
 const stream=fs.createReadStream(file,{start,end});
 if(request.signal){const abort=()=>stream.destroy();request.signal.addEventListener('abort',abort,{once:true});stream.once('close',()=>request.signal.removeEventListener('abort',abort));}
 return new Response(Readable.toWeb(stream),{status,headers});
}
module.exports={mediaResponse};
