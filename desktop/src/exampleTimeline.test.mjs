import test from 'node:test'
import assert from 'node:assert/strict'
import {groupExamples,questionOpening} from './exampleTimeline.ts'
const s=(id,startMs,text)=>({id,startMs,endMs:startMs+900,text})
const n=(id,ss)=>({id,title:'计算步骤'+id,startMs:ss[0].startMs,endMs:ss.at(-1).endMs,children:[],evidenceRefs:ss.map(v=>({sourceType:'transcript',sourceId:v.id,startMs:v.startMs,endMs:v.endMs,quote:v.text}))})
test('one question spans chunks and references to earlier questions do not split it',()=>{
 const ss=[s('1',0,'第一题开始'),s('2',1000,'答案'),s('3',2000,'再来第二题'),s('4',3000,'所以这个题'),s('5',4000,'不是第一题，也不是第二题那样'),s('6',5000,'再往下看第三题'),s('7',6000,'继续计算')]
 const raw=[n('1',ss.slice(0,2)),n('2',ss.slice(2,3)),n('3',ss.slice(3,5)),n('4',ss.slice(5)),n('5',ss.slice(6))]
 const groups=groupExamples(raw,ss);assert.deepEqual(groups.map(v=>v.startMs),[0,2000,5000]);assert.equal(groups[1].endMs,4900);assert.equal(groups[2].evidenceRefs.length,2);assert.deepEqual(groupExamples(groups,ss),groups);assert.equal(raw.length,5)
})
test('without grounded question openings preserve distinct examples',()=>{const ss=[s('1',0,'计算'),s('2',1000,'计算')],raw=[n('1',ss.slice(0,1)),n('2',ss.slice(1))];assert.deepEqual(groupExamples(raw,ss),raw)})
test('ASR numbered transitions require opening cues',()=>{const ss=[s('1',0,'开始'),s('2',1000,'再往下看第七体'),s('3',2000,'第七题和第八题很像'),s('4',3000,'同样再看第八个'),s('5',4000,'再往下再看一个大题题九题')];assert.deepEqual(groupExamples(ss.map((v,i)=>n('n'+i,[v])),ss).map(v=>v.startMs),[0,1000,3000,4000])})

test('bare previous-question reference is not a new problem',()=>{const ss=[s('1',0,'再来看第十一题'),s('2',1000,'第五题'),s('3',2000,'继续讲第十一题')];assert.equal(groupExamples(ss.map((v,i)=>n('n'+i,[v])),ss).length,1)})
test('sparse endpoints cannot lose an intermediate grounded question opening',()=>{const ss=[s('1',0,'第一题开始'),s('2',1000,'再来第二题'),s('3',2000,'再来第三题'),s('4',3000,'计算结果')];const groups=groupExamples([n('1',[ss[0],ss.at(-1)])],ss);assert.deepEqual(groups.map(v=>v.startMs),[0,1000,2000]);assert.equal(groups[1].title,'例题 2')})

test('guard applies to introduction rather than a subsequent comparison',()=>{assert.equal(questionOpening('再看第一题的方法，这个题也可以用洛必达'),null);assert.equal(questionOpening('我们再来看第二题的结论'),null);assert.equal(questionOpening('再看第九题，但不是前面第一题那种做法'),9)})
test('mixed numbered and unnumbered examples retain separate questions',()=>{const ss=[s('1',0,'第一题开始'),s('2',1000,'第一题答案'),s('3',2000,'来看这道例题'),s('4',3000,'第二道题答案'),s('5',4000,'下面看另一个例子')];assert.deepEqual(groupExamples([n('1',ss.slice(0,2)),n('2',ss.slice(2,4)),n('3',ss.slice(4))],ss).map(v=>v.startMs),[0,2000,4000])})

test('rechecking the same question never creates a new entry',()=>{const ss=[s('1',0,'第一题开始'),s('2',1000,'计算分子的极限'),s('3',2000,'再看这道题，分母趋于零，所以用洛必达'),s('4',3000,'代入算出第一题答案')];assert.equal(groupExamples([n('1',ss)],ss).length,1)})
