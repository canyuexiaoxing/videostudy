'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const {createWriteStream,createReadStream} = require('node:fs');
const {pipeline} = require('node:stream/promises');
const {safePath,assertPlain,atomicWrite,digest,relativeName} = require('./storage-paths.cjs');
const HOSTS = new Set(['huggingface.co','hf.co','us.aws.cdn.hf.co','cdn-lfs.huggingface.co','cdn-lfs-us-1.huggingface.co','cdn-lfs-eu-1.huggingface.co','cas-bridge.xethub.hf.co','transfer.xethub.hf.co','paddlex.bj.bcebos.com','github.com','objects.githubusercontent.com','release-assets.githubusercontent.com']);
function trustedUrl(value) {
  const url=new URL(value);
  if(url.protocol!=='https:'||url.username||url.password||url.port||!HOSTS.has(url.hostname))throw Error('untrusted_model_source');
  return url.href;
}
class ModelManager {
  constructor({root,manifest,fetch:fetcher=globalThis.fetch,onProgress=()=>{},timeoutMs=30*60*1000}) {
    this.root=path.resolve(root);this.fetch=fetcher;this.onProgress=onProgress;this.timeoutMs=timeoutMs;this.active=new Map();this.states=new Map();this.verified=new Map();
    const files=Array.isArray(manifest)?manifest:manifest?.files;
    if(!Array.isArray(files))throw Error('invalid_model_manifest');
    this.files=new Map();const names=new Set();
    for(const raw of files) {
      const entry={id:raw.id,relativePath:raw.relativePath,url:raw.url,size:raw.size,sha256:raw.sha256};
      if(typeof entry.id!=='string'||!/^[a-zA-Z0-9._-]+$/.test(entry.id)||this.files.has(entry.id)||!Number.isSafeInteger(entry.size)||entry.size<=0||!/^([a-f0-9]{64})$/.test(entry.sha256))throw Error('invalid_model_manifest');
      relativeName(entry.relativePath);trustedUrl(entry.url);
      const normalized=entry.relativePath.toLowerCase();if(names.has(normalized)||normalized.endsWith('.part')||normalized.endsWith('.download.json'))throw Error('invalid_model_manifest');
      names.add(normalized);this.files.set(entry.id,Object.freeze(entry));
    }
  }
  async _target(entry) {return safePath(this.root,entry.relativePath);}
  async _state(entry,ignoreActive=false) {
    if(!ignoreActive&&this.active.has(entry.id))return {id:entry.id,state:'downloading',...(this.states.get(entry.id)||{}),size:entry.size};
    const target=await this._target(entry);
    try {
      const stat=await fs.stat(target);const identity=`${stat.dev}:${stat.ino}:${stat.size}:${stat.mtimeMs}:${stat.ctimeMs}`;
      let state='corrupt';
      if(stat.isFile()&&stat.size===entry.size){
        const cached=this.verified.get(entry.id);
        if(cached?.identity===identity)state=cached.state;
        else {const hash=await digest(target);const after=await fs.stat(target);const stable=stat.size===after.size&&stat.mtimeMs===after.mtimeMs&&stat.ctimeMs===after.ctimeMs&&stat.ino===after.ino;state=stable&&hash===entry.sha256?'ready':'corrupt';if(stable)this.verified.set(entry.id,{identity,state});}
      }
      return {id:entry.id,state,size:entry.size};
    }
    catch(error){if(error.code==='ENOENT')return {id:entry.id,state:'absent',size:entry.size};throw error;}
  }
  async status(id) {
    if(id!==undefined){const entry=this.files.get(id);if(!entry)throw Error('unknown_model');return this._state(entry);}
    const files=[];for(const entry of this.files.values())files.push(await this._state(entry));
    return {state:files.length&&files.every(f=>f.state==='ready')?'ready':files.some(f=>f.state==='downloading')?'downloading':files.some(f=>f.state==='corrupt')?'corrupt':'absent',files};
  }
  cancel(id) {const controller=this.active.get(id);if(controller){controller.abort();return true;}return false;}
  cancelAll() {for(const controller of this.active.values())controller.abort();}
  async _request(url,options) {
    for(let redirects=0;redirects<6;redirects++) {
      if(options?.signal?.aborted)throw Error('model_cancelled');
      trustedUrl(url);const response=await this.fetch(url,{...options,redirect:'manual'});
      if(response.status>=300&&response.status<400&&response.headers.get('location')) {
        const next=new URL(response.headers.get('location'),url).href;await response.body?.cancel();url=trustedUrl(next);continue;
      }
      if(response.url)trustedUrl(response.url);
      return response;
    }
    throw Error('model_redirect_limit');
  }
  async _space(directory,bytes) {
    if(typeof fs.statfs==='function'){const stat=await fs.statfs(directory);if(stat.bavail*stat.bsize<bytes+64*1024*1024)throw Error('insufficient_disk_space');}
  }
  _progress(id,downloaded,size) {const progress={downloaded,size};this.states.set(id,progress);try{this.onProgress({id,state:'downloading',...progress});}catch{}}
  async install(id) {
    const entry=this.files.get(id);if(!entry)throw Error('unknown_model');if(this.active.has(id))throw Error('model_install_running');
    const controller=new AbortController();this.active.set(id,controller);
    const timeout=setTimeout(()=>controller.abort(),this.timeoutMs);timeout.unref?.();
    let part,meta;
    try {
      if((await this._state(entry,true)).state==='ready')return this._state(entry,true);
      const target=await this._target(entry);await fs.mkdir(path.dirname(target),{recursive:true});
      part=await safePath(this.root,`${entry.relativePath}.part`);meta=await safePath(this.root,`${entry.relativePath}.download.json`);
      let offset=0,etag;
      try {
        const info=JSON.parse(await fs.readFile(meta,'utf8'));const stat=await fs.stat(part);
        if(info.sha256===entry.sha256&&info.size===entry.size&&info.url===entry.url&&typeof info.etag==='string'&&/^"[^\r\n]+"$/.test(info.etag)&&stat.isFile()&&stat.size<=entry.size){offset=stat.size;etag=info.etag;}
      } catch(error){if(error.message==='symlink_forbidden')throw error;}
      if(!offset){await fs.rm(part,{force:true});await fs.rm(meta,{force:true});}
      await this._space(path.dirname(target),entry.size-offset);
      const headers=offset?{Range:`bytes=${offset}-`,'If-Range':etag,'Accept-Encoding':'identity'}:{'Accept-Encoding':'identity'};
      const response=await this._request(entry.url,{headers,signal:controller.signal});
      const incomingEtag=response.headers.get('etag');
      if(response.status===416) {
        await response.body?.cancel();
        if(offset!==entry.size||await digest(part)!==entry.sha256){await fs.rm(part,{force:true});await fs.rm(meta,{force:true});throw Error('invalid_model_range');}
      } else {
        if(response.status!==200&&response.status!==206){await response.body?.cancel();throw Error(`model_http_${response.status}`);}
        if(response.status===206) {
          const range=/^bytes (\d+)-(\d+)\/(\d+)$/.exec(response.headers.get('content-range')||'');
          if(!offset||!range||Number(range[1])!==offset||Number(range[2])!==entry.size-1||Number(range[3])!==entry.size||incomingEtag!==etag){await response.body?.cancel();await fs.rm(part,{force:true});await fs.rm(meta,{force:true});throw Error('invalid_model_range');}
        } else offset=0;
        const length=response.headers.get('content-length');
        if(length!==null&&(!/^\d+$/.test(length)||Number(length)!==entry.size-offset)){await response.body?.cancel();throw Error('invalid_model_length');}
        await atomicWrite(meta,JSON.stringify({url:entry.url,size:entry.size,sha256:entry.sha256,etag:incomingEtag}));
        if(!response.body)throw Error('empty_model_body');
        const handle=await fs.open(part,offset?'a':'w',0o600);let downloaded=offset;
        try {
          for await(const chunk of response.body) {
            if(controller.signal.aborted)throw Error('model_cancelled');
            downloaded+=chunk.byteLength;if(downloaded>entry.size)throw Error('model_too_large');
            let written=0;while(written<chunk.byteLength){const result=await handle.write(chunk,written,chunk.byteLength-written);if(!result.bytesWritten)throw Error('model_write_failed');written+=result.bytesWritten;}
            this._progress(id,downloaded,entry.size);
          }
          await handle.sync();
        } finally {await handle.close();}
        if(downloaded!==entry.size)throw Error('incomplete_model_download');
      }
      if(controller.signal.aborted)throw Error('model_cancelled');
      if(await digest(part)!==entry.sha256){await fs.rm(part,{force:true});await fs.rm(meta,{force:true});throw Error('model_checksum_mismatch');}
      await assertPlain(target);await fs.rename(part,target);await fs.rm(meta,{force:true});
      return {id,state:'ready',size:entry.size};
    } finally {clearTimeout(timeout);this.active.delete(id);this.states.delete(id);}
  }
  async importFile(id,source) {
    const entry=this.files.get(id);if(!entry)throw Error('unknown_model');if(this.active.has(id))throw Error('model_install_running');
    const controller=new AbortController();this.active.set(id,controller);let temp;
    try {
    await assertPlain(source);const stat=await fs.stat(source);if(!stat.isFile()||stat.size!==entry.size)throw Error('invalid_model_size');
    const target=await this._target(entry);await fs.mkdir(path.dirname(target),{recursive:true});await this._space(path.dirname(target),entry.size);
    temp=await safePath(this.root,`${entry.relativePath}.${crypto.randomUUID()}.part`);
    await pipeline(createReadStream(source),createWriteStream(temp,{flags:'wx',mode:0o600}),{signal:controller.signal});if(await digest(temp)!==entry.sha256)throw Error('model_checksum_mismatch');await assertPlain(target);await fs.rename(temp,target);return {id,state:'ready',size:entry.size};}
    finally{this.active.delete(id);if(temp)await fs.rm(temp,{force:true});}
  }
}
module.exports={ModelManager,trustedUrl};


