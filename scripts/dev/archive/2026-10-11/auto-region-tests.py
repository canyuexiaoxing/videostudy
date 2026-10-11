from pathlib import Path
p=Path('E:/workp/videostudy')
files={
'docs/superpowers/specs/2026-10-11-auto-region.md':'''# 四点递归自动框选
用户已授权实施：初始开头、1/3、2/3、结尾四帧，区域不同才取中点递归，到30秒以内停止。位置变化时间采用区间中点估计；相同端点间短暂变化可能漏检。
浏览器独立视频元素取960px长边JPEG，不上传整片。每批最多4帧经Java代理调用Python已有视觉API配置；模型只返回detected/absent/uncertain及完整摄像头窗口归一化坐标，时间绑定请求值。手/笔/课件不做忽略。
客户端编排最多64帧，缓存时间结果、支持取消、关闭/换文件取消并丢弃迟到结果。未知区间暂停忽略并明确展示；不得当成确认不存在。候选设置独立预览，不写当前设置；应用才替换，手动可修正。截图外发提示在按钮附近显示。
复用现有nodes参数、存储和后端粗选，不改变首次手动框选规则。测试用注入识别结果，不擅自触发付费整课测试。
''',
'docs/superpowers/plans/2026-10-11-auto-region.md':'''# 自动框选 Implementation Plan
Goal: four initial images and selective recursion produce previewable30s timeline.
Architecture: local browser JPEG capture; Java proxy; Python bounded vision detection; pure client scanner; existingregionnodes reused.
Spec: ../specs/2026-10-11-auto-region.md
- [ ] Red/green pure scanner tests: fourpoints, stable, switches, unknown, budget/cancellation.
- [ ] Python detectvalidation+provider tests; Java proxy/validationtests.
- [ ] Workspace controls, cancel and candidatepreview/apply; localshortvideo browser QA.
- [ ] Fullregression, review, localdeployment andhandoff. No unsolicitedcommit/push.
''',
'desktop/src/autoRegionScan.test.mjs':'''import {test} from 'node:test'
import assert from 'node:assert/strict'
import {scanRegions} from './autoRegionScan.ts'
const A={x:.7,y:.6,width:.2,height:.3},B={x:.1,y:.1,width:.2,height:.2}
const d=(timeMs,region=A)=>({timeMs,status:region?'detected':'absent',region})
test('stable four-point scan only inspects beginning thirds and last frame',async()=>{
 const calls=[];const r=await scanRegions(90000,async times=>{calls.push(...times);return times.map(t=>d(t))})
 assert.deepEqual(calls,[0,30000,60000,89900]);assert.equal(r.setting.nodes.length,1);assert.deepEqual(r.setting.nodes[0],{timeMs:0,region:A})
})
test('only changing intervals recurse until30seconds and restore absence',async()=>{
 const calls=[];const r=await scanRegions(360000,async times=>{calls.push(...times);return times.map(t=>d(t,t<75000?A:t<250000?B:null))})
 assert(calls.length>4);assert(!calls.includes(180000));assert.equal(r.setting.nodes.length,3)
 assert(Math.abs(r.setting.nodes[1].timeMs-75000)<=15000);assert(Math.abs(r.setting.nodes[2].timeMs-250000)<=15000)
 assert.equal(r.setting.nodes[2].region,null)
})
test('uncertainty never turns into confirmed absence',async()=>{
 const r=await scanRegions(90000,async times=>times.map(t=>t===30000?{timeMs:t,status:'uncertain',region:null}:d(t)))
 assert(r.unresolved.length>0);assert.equal(r.setting.nodes[0].region,null)
})
test('malformed batch cannot create a candidate and cancellation stops',async()=>{
 await assert.rejects(scanRegions(90000,async times=>times.map(t=>d(t+1))))
 const c=new AbortController();c.abort();await assert.rejects(scanRegions(90000,async()=>[],{signal:c.signal}),{name:'AbortError'})
})
''',
'agent-python/test_auto_region.py':'''import base64,io,unittest
from PIL import Image
from auto_region import detect_frames,normalize_detection
class AutoRegionTest(unittest.TestCase):
 def image(self):
  out=io.BytesIO();Image.new('RGB',(100,80),'white').save(out,format='JPEG');return 'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()
 def test_coordinates_and_timestamp_are_validated(self):
  r=normalize_detection({'status':'detected','region':dict(x=.7,y=.6,width=.2,height=.3)},42)
  self.assertEqual(r['timeMs'],42)
  self.assertEqual(normalize_detection({'status':'detected','region':dict(x=2,y=0,width=.1,height=.1)},42)['status'],'uncertain')
  self.assertEqual(normalize_detection({'status':'absent','region':None},42)['status'],'absent')
 def test_batch_preserves_times_and_does_not_call_on_invalid_images(self):
  calls=[]
  result=detect_frames([dict(timeMs=t,image=self.image()) for t in [0,2000]],ask=lambda image: calls.append(image) or {'status':'absent','region':None})
  self.assertEqual([r['timeMs'] for r in result],[0,2000]);self.assertEqual(len(calls),2)
  for frames in [[],[dict(timeMs=0,image='bad')],[dict(timeMs=-1,image=self.image())],[dict(timeMs=0,image=self.image())]*2]:
   with self.assertRaises(ValueError):detect_frames(frames,ask=lambda _: self.fail('invalid input must not call provider'))
'''
}
for name,body in files.items():
 target=p/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(body,encoding='utf-8')
