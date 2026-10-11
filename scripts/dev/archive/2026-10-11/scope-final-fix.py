from pathlib import Path
root=Path(r'E:\workp\videostudy')
p=root/'agent-python/mind_map.py';s=p.read_text(encoding='utf-8').replace('r"本题|该题','r"(?<!基)本题|该题').replace('|本例|此例|','|(?<!基)本例|此例|')
s=s.replace('''            if concepts:
                chapter_title''','''            pending = list(concepts)
            while pending:
                node = pending.pop()
                node['_dedicatedSourceIds'] = sorted(teaching_ids) if classified else None
                pending.extend(node['children'])
            if concepts:
                chapter_title''')
p.write_text(s,encoding='utf-8')
p=root/'agent-python/test_core_mind_map.py'
with p.open('a',encoding='utf-8') as f:
 f.write('''
 def test_basic_question_types_are_not_a_reference_to_this_question(self):
  result=build_mind_map([segment(1,'增长量计算的基本题型有两种')],[],lambda _: {'topic':'课程','children':[{'title':'基本题型','kind':'knowledge','sourceIds':['t_1']}],'examples':[],'teachingSourceIds':['t_1'],'exampleSourceIds':[]})
  self.assertEqual(result['status'],'completed')
  self.assertEqual(result['examples'],[])
''')
p=root/'desktop/src/AiPractice.vue';s=p.read_text(encoding='utf-8').replace('  <label v-if="sets.length"', '  <p v-if="courseId&&!demo" class="practice-intro">按完整知识分支练习，包含下级公式、条件和易错点。</p>\n  <label v-if="sets.length"');p.write_text(s,encoding='utf-8')
stage=Path(__file__).parent
s=(stage/'core-map-ui.mjs').read_text()
s=s.replace('children:[leaf]},examples:[example]', "children:[{...leaf,id:'topic',title:'增长量计算',children:[{...leaf,id:'detail',title:'公式细节',children:[leaf]},{...leaf,id:'condition',title:'适用条件'}]}]},examples:[example]")
s=s.replace("route.fulfill({status:404,json:{error:'qa_no_other_calls'}})","route.fulfill({json:[]})")
start=s.index(" await page.locator('.example-timeline').waitFor();")
s=s[:start]+'''
 await page.getByRole('tab',{name:'AI 练习',exact:true}).click();
 const scope=page.getByLabel('练习范围',{exact:true});
 assert.deepEqual(await scope.locator('option').evaluateAll(opts=>opts.map(o=>o.value)),['','topic']);
 await page.evaluate(()=>{const s=document.querySelector('#app').__vue_app__._instance.setupState;s.selectedMindNode=s.mindMap.root.children[0].children[0].children[0]});
 await page.waitForFunction(()=>document.querySelector('.practice-settings select')?.value==='topic');
 let payload;
 await page.route(`**/api/transcriptions/${id}/practice`,route=>{if(route.request().method()==='POST'){payload=route.request().postDataJSON();return route.fulfill({json:{id:'fixture',title:'增长量计算',status:'completed',questions:[]}})}return route.fulfill({json:[]})});
 await page.getByRole('button',{name:'生成练习',exact:true}).click();
 await page.waitForTimeout(150);assert.equal(payload.nodeId,'topic');
 await page.evaluate(()=>{const s=document.querySelector('#app').__vue_app__._instance.setupState;s.selectedMindNode=null;s.mindMap={...s.mindMap,root:{...s.mindMap.root,children:[]}}});
 await page.waitForFunction(()=>document.querySelector('.practice-settings select')?.value==='');
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({branchOptions:true,leafSelectsAncestor:true,requestUsesTopic:true,mapChangeResetsScope:true,realModelCalls:0}));
}finally{await browser.close();}
'''
(stage/'scope-ui.mjs').write_text(s)
