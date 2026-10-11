import test from 'node:test'
import assert from 'node:assert/strict'
import { practiceScopes, resolvePracticeScope } from './practiceScope.ts'
const leaf=(id)=>({id,title:id,children:[]})
const root={id:'root',title:'课程',children:[{id:'topic',title:'增长量',children:[{id:'formula',title:'公式细节',children:[leaf('a')]},leaf('b')]},{id:'other',title:'增长率',children:[leaf('c'),leaf('d')]}]}
test('practice options exclude leaves and singleton detail branches',()=>assert.deepEqual(practiceScopes(root).map(n=>n.id),['topic','other']))
test('leaf selection rises through a singleton parent to the full topic',()=>{assert.equal(resolvePracticeScope(root,'a'),'topic');assert.equal(resolvePracticeScope(root,'b'),'topic');assert.equal(resolvePracticeScope(root,'topic'),'topic')})
test('whole course and stale node selections resolve to whole course',()=>{assert.equal(resolvePracticeScope(root,''),'');assert.equal(resolvePracticeScope(root,'old'), '');assert.equal(resolvePracticeScope(undefined,'a'),'')})
test('a course with one detail supports whole-course practice',()=>{const single={id:'root',title:'课程',children:[{id:'one',title:'单个主题',children:[leaf('a')]}]};assert.deepEqual(practiceScopes(single),[]);assert.equal(resolvePracticeScope(single,'a'),'')})
