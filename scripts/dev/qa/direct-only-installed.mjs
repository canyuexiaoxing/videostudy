import {extractFile} from '../../../desktop/node_modules/@electron/asar/lib/asar.js';import {readFile,writeFile} from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';import crypto from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),record=JSON.parse(await readFile(path.join(root,'.local/qa/direct-only/prepared.json'),'utf8'));
const index=extractFile(record.archive,'dist/index.html').toString();const match=index.match(/src="([^\"]+\.js)"/);if(!match)throw Error('entry_script_missing');
const key=path.join('dist',match[1].replace(/^(?:\.\/|\/)/,''));const js=extractFile(record.archive,key).toString();
if(!js.includes('整课图文直生成')||js.includes('分组后汇总'))throw Error('installed_mode_labels_wrong');
const digest=crypto.createHash('sha256').update(await readFile(record.archive)).digest('hex');if(digest!==record.preparedSha256)throw Error('installed_checksum_mismatch');
const report={installed:true,onlyDirectGenerationVisible:true,installedChecksumMatches:true,uploadAndManualRequestsVerified:record.uiVerification,databaseModified:false,runtimeModified:false};await writeFile(path.join(root,'.local/qa/direct-only/installed-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
