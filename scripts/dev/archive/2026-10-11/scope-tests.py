from pathlib import Path
root=Path(r'E:\workp\videostudy')
(root/'desktop/src/practiceScope.test.mjs').write_text('''import test from 'node:test'
import assert from 'node:assert/strict'
import { practiceScopes, resolvePracticeScope } from './practiceScope.ts'
const leaf=(id)=>({id,title:id,children:[]})
const root={id:'root',title:'课程',children:[{id:'topic',title:'增长量',children:[{id:'formula',title:'公式细节',children:[leaf('a')]},leaf('b')]},{id:'other',title:'增长率',children:[leaf('c'),leaf('d')]}]}
test('practice options exclude leaves and singleton detail branches',()=>assert.deepEqual(practiceScopes(root).map(n=>n.id),['topic','other']))
test('leaf selection rises through a singleton parent to the full topic',()=>{assert.equal(resolvePracticeScope(root,'a'),'topic');assert.equal(resolvePracticeScope(root,'b'),'topic');assert.equal(resolvePracticeScope(root,'topic'),'topic')})
test('whole course and stale node selections resolve to whole course',()=>{assert.equal(resolvePracticeScope(root,''),'');assert.equal(resolvePracticeScope(root,'old'), '');assert.equal(resolvePracticeScope(undefined,'a'),'')})
test('a course with one detail supports whole-course practice',()=>{const single={id:'root',title:'课程',children:[{id:'one',title:'单个主题',children:[leaf('a')]}]};assert.deepEqual(practiceScopes(single),[]);assert.equal(resolvePracticeScope(single,'a'),'')})
''',encoding='utf-8')
p=root/'backend-java/src/test/java/cn/videostudy/api/PracticeControllerTest.java';s=p.read_text(encoding='utf-8');i=s.rfind('}');s=s[:i]+'''
    @Test void leafPracticeExpandsToParentTopicAndSiblingEvidence() {
        var a=course().mindMap().root().children().getFirst();
        var b=new MindMapNode("n2","适用条件",1000,2000,List.of(new MindMapEvidence("transcript","s2",1000,2000,"适用条件")),List.of());
        var single=new MindMapNode("detail","公式细节",0,1000,List.of(),List.of(a));
        var topic=new MindMapNode("topic","增长量计算",0,2000,List.of(),List.of(single,b));
        var root=new MindMapNode("root","课程",0,2000,List.of(),List.of(topic));
        var result=new TranscriptResult("zh",List.of(new TranscriptSegment("s1",0,1000,"增长量公式"),new TranscriptSegment("s2",1000,2000,"适用条件")),List.of(),null,null,null).withMindMap(new MindMapResult("completed","model","v1",root));
        var source=PracticeController.source(result,new PracticeController.Request("n1",3,"basic",false));
        assertEquals(2,((List<?>)source.get("nodes")).size());
        assertEquals("topic",source.get("scopeNodeId"));assertEquals("增长量计算",source.get("scopeTitle"));
        assertEquals(source,PracticeController.source(result,new PracticeController.Request("topic",3,"basic",false)));
    }
'''+s[i:];p.write_text(s,encoding='utf-8')
p=root/'agent-python/test_core_mind_map.py'
with p.open('a',encoding='utf-8') as f:
 f.write('''
 def test_case_specific_leaf_cannot_be_whitelisted_as_teaching(self):
  result=build_mind_map([segment(1,'先讲公式'),segment(8,'这一道题要注意2014年开头')],[],lambda _: {'topic':'课程','children':[{'title':'公式','sourceIds':['t_1']},{'title':'本题2014年开头要验证基期','kind':'knowledge','sourceIds':['t_8']}],'examples':[],'teachingSourceIds':['t_1','t_8'],'exampleSourceIds':[]})
  self.assertEqual([n['title'] for n in result['root']['children'][0]['children']],['公式'])
  self.assertEqual(len(result['examples']),1)

 def test_case_specific_quote_is_filtered_even_under_general_title(self):
  result=build_mind_map([segment(1,'先讲公式'),segment(8,'这道题算出来是20')],[],lambda _: {'topic':'课程','children':[{'title':'公式','sourceIds':['t_1','t_8']}],'examples':[],'teachingSourceIds':['t_1','t_8'],'exampleSourceIds':[]})
  self.assertEqual([ref['sourceId'] for ref in result['root']['children'][0]['children'][0]['evidenceRefs']],['t_1'])
''')
