'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { createReadStream } = require('node:fs');

function relativeName(value) {
  if (typeof value !== 'string' || !value || value.includes('\\') || path.posix.isAbsolute(value) || /^[a-z]:/i.test(value)) throw Error('unsafe_path');
  const parts = value.split('/');
  if (parts.some(p => !p || p === '.' || p === '..' || /[<>:"|?*\x00-\x1f]/.test(p) || /[. ]$/.test(p) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(p))) throw Error('unsafe_path');
  return parts.join(path.sep);
}
async function assertPlain(target) {
  const absolute = path.resolve(target);
  const parsed = path.parse(absolute);
  let current = parsed.root;
  for (const part of absolute.slice(parsed.root.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    try { const stat = await fs.lstat(current); if (stat.isSymbolicLink()) throw Error('symlink_forbidden'); }
    catch (error) { if (error.code === 'ENOENT') break; throw error; }
  }
  return absolute;
}
async function safePath(root, relative) {
  const target = path.join(path.resolve(root), relativeName(relative));
  await assertPlain(target);
  return target;
}
async function atomicWrite(target, content) {
  await assertPlain(target);
  await fs.mkdir(path.dirname(target), {recursive:true});
  const temp = `${target}.${crypto.randomUUID()}.tmp`;
  try { await fs.writeFile(temp, content, {flag:'wx',mode:0o600}); await fs.rename(temp, target); }
  finally { await fs.rm(temp, {force:true}); }
}
async function digest(file) {
  await assertPlain(file);
  const hash = crypto.createHash('sha256');
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}
async function walk(root, prefix = '') {
  await assertPlain(root);
  const result = [];
  for (const entry of await fs.readdir(root, {withFileTypes:true})) {
    const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
    relativeName(relative);
    const file = await safePath(root, entry.name);
    if (entry.isSymbolicLink()) throw Error('symlink_forbidden');
    if (entry.isDirectory()) result.push(...await walk(file, relative));
    else if (entry.isFile()) result.push({relative, file});
    else throw Error('special_file_forbidden');
  }
  return result;
}
module.exports = {relativeName,assertPlain,safePath,atomicWrite,digest,walk};
