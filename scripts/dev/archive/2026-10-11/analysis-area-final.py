from pathlib import Path
p=Path('E:/workp/videostudy/desktop/src')
f=p/'videoRegionTimeline.ts'
f.write_text(f.read_text()+'''\nexport function validateRegionCombination(analysis: IgnoreSetting | null, ignored: IgnoreSetting | null): void {
  const times = new Set([0, ...regionNodes(analysis).map(n => n.timeMs), ...regionNodes(ignored).map(n => n.timeMs)])
  for (const time of times) {
    const a = regionAt(analysis, time), b = regionAt(ignored, time)
    if (a && b && b.x <= a.x && b.y <= a.y && b.x+b.width >= a.x+a.width && b.y+b.height >= a.y+a.height)
      throw new Error(`忽略框在 ${Math.floor(time/1000)} 秒覆盖了整个分析区域，请调整区域或时间节点`)
  }
}
''',encoding='utf-8')
f=p/'videoRegionTimeline.test.mjs'
s=f.read_text().replace('normalizeIgnoreSetting, regionAt','validateRegionCombination, normalizeIgnoreSetting, regionAt')
s+='''\ntest('combined validation checks first baseline and all later boundaries',()=>{
 const board={x:.2,y:.2,width:.3,height:.3}, cover={x:.1,y:.1,width:.5,height:.5}, outside={x:.8,y:.8,width:.1,height:.1}
 const ignored=upsertRegionNode(cover,8000,outside)
 assert.throws(()=>validateRegionCombination(upsertRegionNode(null,10000,board,true),ignored),/0 秒/)
 assert.doesNotThrow(()=>validateRegionCombination(board,outside))
 assert.doesNotThrow(()=>validateRegionCombination(board,{x:.4,y:.4,width:.3,height:.3}))
 const analysis=upsertRegionNode(null,0,board,true)
 assert.throws(()=>validateRegionCombination(analysis,cover),/覆盖/)
 const safe=upsertRegionNode(cover,4000,outside)
 const later={nodes:[{timeMs:0,region:null},{timeMs:5000,region:board}]}
 assert.doesNotThrow(()=>validateRegionCombination(later,safe))
 assert.throws(()=>validateRegionCombination(later,removeRegionNode(safe,4000)),/5 秒/)
})
'''
f.write_text(s,encoding='utf-8')
f=p/'VideoWorkspace.vue';s=f.read_text().replace('regionAt,regionNodes,upsertRegionNode,removeRegionNode','validateRegionCombination,regionAt,regionNodes,upsertRegionNode,removeRegionNode')
s=s.replace("function commitRegion(value:IgnoreSetting|null){if(areaMode.value==='analysis')emit('update:analysisRegion',value);else emit('update:modelValue',value)}",'''function commitRegion(value:IgnoreSetting|null){
 try{validateRegionCombination(areaMode.value==='analysis'?value:props.analysisRegion,areaMode.value==='ignore'?value:props.modelValue)}
 catch(e){refresh();error.value=e instanceof Error?e.message:'区域设置冲突';return false}
 if(areaMode.value==='analysis')emit('update:analysisRegion',value);else emit('update:modelValue',value)
 return true
}''')
s=s.replace("  commitRegion(upsertRegionNode(selectedSetting.value,finished.timeMs,draft.value,areaMode.value==='analysis'))","  if(!commitRegion(upsertRegionNode(selectedSetting.value,finished.timeMs,draft.value,areaMode.value==='analysis')))return")
s=s.replace('draft.value=null;commitRegion(null);','draft.value=null;if(!commitRegion(null))return;').replace('commitRegion(removeRegionNode(selectedSetting.value,timeMs));','if(!commitRegion(removeRegionNode(selectedSetting.value,timeMs)))return;')
s=s.replace("const value=candidate.value.setting;candidate.value=null;emit('update:modelValue',value);", "const value=candidate.value.setting;try{validateRegionCombination(props.analysisRegion,value)}catch(e){error.value=e instanceof Error?e.message:'区域设置冲突';return}candidate.value=null;emit('update:modelValue',value);")
f.write_text(s,encoding='utf-8')
