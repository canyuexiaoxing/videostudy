import test from 'node:test'
import assert from 'node:assert/strict'
import { practiceScopes, resolvePracticeScope, practiceScopeTree } from './practiceScope.ts'
const leaf=(id)=>({id,title:id,children:[]})
const root={id:'root',title:'课程',children:[{id:'topic',title:'增长量',children:[{id:'formula',title:'公式细节',children:[leaf('a')]},leaf('b')]},{id:'other',title:'增长率',children:[leaf('c'),leaf('d')]}]}
test('practice options exclude leaves and singleton detail branches',()=>assert.deepEqual(practiceScopes(root).map(n=>n.id),['topic','other']))
test('leaf selection rises through a singleton parent to the full topic',()=>{assert.equal(resolvePracticeScope(root,'a'),'topic');assert.equal(resolvePracticeScope(root,'b'),'topic');assert.equal(resolvePracticeScope(root,'topic'),'topic')})
test('whole course and stale node selections resolve to whole course',()=>{assert.equal(resolvePracticeScope(root,''),'');assert.equal(resolvePracticeScope(root,'old'), '');assert.equal(resolvePracticeScope(undefined,'a'),'')})
test('a course with one detail supports whole-course practice',()=>{const single={id:'root',title:'课程',children:[{id:'one',title:'单个主题',children:[leaf('a')]}]};assert.deepEqual(practiceScopes(single),[]);assert.equal(resolvePracticeScope(single,'a'),'')})


test('explicit details select their concept including image-only concepts',()=>{
 const concept={id:'concept',title:'图中概念',children:[],details:[leaf('detail')]}
 const course={id:'root',title:'课程',children:[concept]}
 assert.deepEqual(practiceScopes(course).map(n=>n.id),['concept'])
 assert.equal(resolvePracticeScope(course,'detail'),'concept')
})


test('scope tree shows modules first and nests selectable subranges without details',()=>{
 const small={id:'small',title:'分类方法',children:[],details:[leaf('condition')]}
 const course={id:'root',title:'课程',children:[{id:'module',title:'计算',children:[small,leaf('plain')]}]}
 const tree=practiceScopeTree(course)
 assert.deepEqual(tree.map(n=>n.id),['module']);assert.deepEqual(tree[0].children.map(n=>n.id),['small'])
 assert.equal(tree[0].children[0].details,undefined);assert.equal(small.details.length,1)
})
test('scope tree retains a standalone module and returns no stale scopes for missing course',()=>{
 assert.deepEqual(practiceScopeTree({id:'root',title:'课',children:[leaf('module')]}).map(n=>n.id),['module'])
 assert.deepEqual(practiceScopeTree(undefined),[])
})
