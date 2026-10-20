'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const {assertPlain,atomicWrite} = require('./storage-paths.cjs');
const DIRECTORIES = ['database','models','uploads','keyframes','logs','backups','cache'];
function validateSettings(input, previous) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw Error('invalid_settings');
  const device = input.device ?? previous.device;
  if (!['auto','gpu','cpu'].includes(device)) throw Error('invalid_device');
  const source = input.deepseek ?? {};
  if (!source || typeof source !== 'object' || Array.isArray(source)) throw Error('invalid_deepseek');
  const baseUrl = source.baseUrl ?? previous.deepseek.baseUrl;
  let url; try { url = new URL(baseUrl); } catch { throw Error('invalid_api_url'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.hostname !== 'api.deepseek.com') throw Error('invalid_api_url');
  const model = source.model ?? previous.deepseek.model;
  if (typeof model !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$/.test(model)) throw Error('invalid_model');
  return {schemaVersion:1,device,deepseek:{baseUrl:url.href.replace(/\/$/,''),model}};
}
class LocalStorage {
  constructor({root,safeStorage}) {
    if (!path.isAbsolute(root)) throw Error('absolute_root_required');
    this.root=path.resolve(root); this.safeStorage=safeStorage;
    this.paths=Object.fromEntries(DIRECTORIES.map(name=>[name,path.join(this.root,name)]));
    this.settingsFile=path.join(this.root,'settings.json');
  }
  async init() {
    await assertPlain(this.root); await fs.mkdir(this.root,{recursive:true});
    for (const directory of Object.values(this.paths)) { await assertPlain(directory); await fs.mkdir(directory,{recursive:true}); }
    return this.getSettings();
  }
  async _read() {
    await assertPlain(this.settingsFile);
    try {
      if((await fs.stat(this.settingsFile)).size>32768)throw Error('settings_too_large');
      const text=await fs.readFile(this.settingsFile,'utf8');
      if (text.length>32768) throw Error('settings_too_large');
      const raw=JSON.parse(text); const validated=validateSettings(raw,LocalStorage.defaults());
      if (raw.schemaVersion !== 1 || (raw.encryptedKey !== undefined && (typeof raw.encryptedKey!=='string' || raw.encryptedKey.length>16384))) throw Error('invalid_settings');
      return {...validated,...(raw.encryptedKey?{encryptedKey:raw.encryptedKey}:{})};
    } catch(error) { if(error.code==='ENOENT')return LocalStorage.defaults(); throw error; }
  }
  static defaults() {return {schemaVersion:1,device:'auto',deepseek:{baseUrl:'https://api.deepseek.com',model:'deepseek-flash'}};}
  async getSettings() {const value=await this._read();return {schemaVersion:value.schemaVersion,device:value.device,deepseek:{...value.deepseek,hasKey:!!value.encryptedKey},encryptionAvailable:!!this.safeStorage?.isEncryptionAvailable()};}
  async saveSettings(input) {
    const previous=await this._read(); const next=validateSettings(input,previous);
    if(previous.encryptedKey)next.encryptedKey=previous.encryptedKey;
    if(Object.hasOwn(input.deepseek??{},'apiKey')) {
      const key=input.deepseek.apiKey;
      if(typeof key!=='string'||key.length>4096||/[\r\n\x00]/.test(key))throw Error('invalid_api_key');
      if(key) {
        if(!this.safeStorage?.isEncryptionAvailable())throw Error('secure_storage_unavailable');
        next.encryptedKey=this.safeStorage.encryptString(key).toString('base64');
      } else delete next.encryptedKey;
    }
    await atomicWrite(this.settingsFile,JSON.stringify(next,null,2));return this.getSettings();
  }
  async getApiKey() {
    const value=await this._read();if(!value.encryptedKey)return '';
    if(!this.safeStorage?.isEncryptionAvailable())throw Error('secure_storage_unavailable');
    return this.safeStorage.decryptString(Buffer.from(value.encryptedKey,'base64'));
  }
}
module.exports={LocalStorage,DIRECTORIES,validateSettings};

