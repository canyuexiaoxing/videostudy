from pathlib import Path
root=Path(r'E:\workp\videostudy')
p=root/'agent-python/mind_map.py'
s=p.read_text(encoding='utf-8').replace("return raw.get('kind') == 'example' or bool(re.match(","if raw.get('kind') == 'knowledge': return False\n                return raw.get('kind') == 'example' or bool(re.match(")
s=s.replace('return {"chapter": None, "failed": True, "examples": []}\n            return', 'return {"chapter": None, "failed": True, "examples": examples}\n            return')
p.write_text(s,encoding='utf-8')
p=root/'desktop/src/App.vue';s=p.read_text(encoding='utf-8').replace('@click="selectMindMapNode(example)"','@click="seekTo(example.evidenceRefs[0]?.startMs ?? example.startMs, example.evidenceRefs[0]?.sourceId)"');p.write_text(s,encoding='utf-8')
p=root/'backend-java/src/main/java/cn/videostudy/api/MindMapController.java';s=p.read_text(encoding='utf-8').replace('!"completed".equals(generated.status()))','!"completed".equals(generated.status()) &&\n                !("empty".equals(generated.status()) && generated.examples() != null && !generated.examples().isEmpty()))');p.write_text(s,encoding='utf-8')
p=root/'agent-python/test_core_mind_map.py';s=p.read_text(encoding='utf-8');s+='''
 def test_general_formula_from_example_remains_core(self):
  result=build_mind_map([segment(1,'通用公式')],[],lambda _: {'topic':'公式','children':[{'title':'例题中的通用公式','kind':'knowledge','sourceIds':['t_1']}],'examples':[]})
  self.assertEqual(result['status'],'completed')
  self.assertEqual(result['root']['children'][0]['children'][0]['title'],'例题中的通用公式')
  self.assertEqual(result['examples'],[])

 def test_valid_examples_survive_invalid_core(self):
  result=build_mind_map([segment(1,'例题一')],[],lambda _: {'topic':'课程','children':[{'title':'概念','sourceIds':['unknown']}],'examples':[{'title':'例题一','sourceIds':['t_1']}]})
  self.assertEqual(result['status'],'failed')
  self.assertEqual(len(result['examples']),1)
''';p.write_text(s,encoding='utf-8')
p=root/'backend-java/src/test/java/cn/videostudy/api/MindMapExamplesTest.java';s=p.read_text(encoding='utf-8');idx=s.rfind('}');s=s[:idx]+'''
 @Test void refreshCanMigrateOldExampleMapToIndependentTimeline() {
  var speech=List.of(new TranscriptionController.TranscriptSegment("s1",1000,2000,"例题一"));
  var ref=new TranscriptionController.MindMapEvidence("transcript","s1",1000,2000,"例题一");
  var example=new TranscriptionController.MindMapNode("example1","例题一",1000,2000,List.of(ref),List.of());
  var oldRoot=new TranscriptionController.MindMapNode("course","课程知识导图",1000,2000,List.of(ref),List.of(example));
  var oldMap=new TranscriptionController.MindMapResult("completed",null,null,"v2",null,oldRoot);
  var result=new TranscriptionController.TranscriptResult("zh",speech,List.of(),null,null,null).withMindMap(oldMap);
  var emptyRoot=new TranscriptionController.MindMapNode("course","课程知识导图",0,0,List.of(),List.of());
  var generated=new TranscriptionController.MindMapResult("empty",null,null,"v3",null,emptyRoot,List.of(example));
  var store=org.mockito.Mockito.mock(TranscriptionJobStore.class);
  var analyzer=org.mockito.Mockito.mock(MediaAnalyzer.class);
  org.mockito.Mockito.when(store.find("job")).thenReturn(java.util.Optional.of(new TranscriptionController.TranscriptionJob("job","completed",result,null)));
  org.mockito.Mockito.when(analyzer.generateMindMap(org.mockito.ArgumentMatchers.anyList(),org.mockito.ArgumentMatchers.anyList())).thenReturn(generated);
  assertEquals(200,new MindMapController(store,analyzer).generate("job",true).getStatusCode().value());
  org.mockito.Mockito.verify(store).saveMindMap("job",generated);
 }
'''+s[idx:];p.write_text(s,encoding='utf-8')
stage=Path(__file__).parent
s=(stage/'progress-deploy.py').read_text().replace('progress-images','core-map-images').replace("'analysis_progress.py')","'analysis_progress.py','mind_map.py')").replace('analysis_progress.py /app/','analysis_progress.py mind_map.py /app/')
(stage/'core-map-deploy.py').write_text(s)
