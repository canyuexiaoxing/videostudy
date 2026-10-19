const fs=require('node:fs/promises');const path=require('node:path');const crypto=require('node:crypto');
async function fingerprint(file){const handle=await fs.open(file,'r');try{const before=await handle.stat();if(!before.isFile())throw Error('not_media_file');const size=before.size,first=Buffer.alloc(Math.min(size,65536)),last=Buffer.alloc(Math.min(size,65536));await handle.read(first,0,first.length,0);await handle.read(last,0,last.length,Math.max(0,size-65536));const length=Buffer.alloc(8);length.writeBigUInt64BE(BigInt(size));const after=await handle.stat();if(before.size!==after.size||before.mtimeMs!==after.mtimeMs)throw Error('media_changed');return {size,fingerprint:crypto.createHash('sha256').update(length).update(first).update(last).digest('hex')};}finally{await handle.close()}}
class MediaLibrary{
 constructor(profile){this.file=path.join(profile,'media-library.json');this.tokens=new Map();this.queue=Promise.resolve()}
 async records(){try{return JSON.parse(await fs.readFile(this.file,'utf8'))}catch{return {}}}
 async register(file){file=path.resolve(file);const metadata=await fingerprint(file);const token=crypto.randomUUID();this.tokens.set(token,file);const save=async()=>{const records=await this.records();records[metadata.fingerprint]=file;await fs.mkdir(path.dirname(this.file),{recursive:true});await fs.writeFile(this.file+'.tmp',JSON.stringify(records));await fs.rename(this.file+'.tmp',this.file)};this.queue=this.queue.then(save,save);await this.queue;return {...metadata,name:path.basename(file),url:'app://framewise/media/'+token}}
 async restore(fp){if(!/^[a-f0-9]{64}$/.test(fp))return null;try{const file=(await this.records())[fp];if(typeof file!=='string')return null;const current=await fingerprint(file);if(current.fingerprint!==fp)return null;return await this.register(file)}catch{return null}}
 pathFor(token){return this.tokens.get(token)||null}
}
module.exports={fingerprint,MediaLibrary};
