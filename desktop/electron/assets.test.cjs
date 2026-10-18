const test=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const {assetPath,allowedNavigation}=require('./assets.cjs');
test('desktop routes resolve only packaged frontend assets',()=>{
 const root=path.resolve('example-dist');assert.equal(assetPath('app://framewise/',root),path.join(root,'index.html'));
 assert.equal(assetPath('app://framewise/assets/app.js',root),path.join(root,'assets','app.js'));
 for(const url of ['app://other/index.html','file:///secret','app://framewise/%2e%2e%5csecret.txt','app://framewise/.env','app://framewise/package.json','app://framewise/%00.png'])assert.equal(assetPath(url,root),null,url);
});
test('desktop windows cannot navigate to arbitrary websites or local files',()=>{
 assert.equal(allowedNavigation('app://framewise/index.html',false),true);
 assert.equal(allowedNavigation('http://127.0.0.1:5173/',true),true);
 for(const u of ['https://example.com','file:///C:/secret','app://other/','http://127.0.0.1:5173/'])assert.equal(allowedNavigation(u,false),false,u);
});
