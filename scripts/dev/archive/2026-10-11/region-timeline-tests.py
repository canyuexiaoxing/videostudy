from pathlib import Path
root=Path(r'E:\workp\videostudy')
plan=root/'docs/superpowers/plans/2026-10-11-ignore-region-timeline.md'
plan.parent.mkdir(parents=True,exist_ok=True)
plan.write_text('''# 忽略区域时间节点执行计划

已确认需求：第一次框选应用全片（0ms）；之后在当前视频时间完成框选、移动或缩放时自动新增节点，同一时间更新，直到下一节点生效。提供时间列表跳转和删除后续节点，清除全部；第一节点保留0ms。视频文件指纹隔离设置。

1. 新增前端 timeline 工具，兼容固定区域；先测首节点、后续、同时间覆盖、删除和非法时间。
2. 工作台复用框选叠层，加入移动和右下角缩放手柄，松手自动保存；拖动时间固定于起始帧，暂停播放。预览按时间切框，显示节点列表。
3. Java IgnoreRegion 兼容固定区域和 nodes 信封，通过既有 ignored_region_json、请求、重试链路存储转发，无数据库迁移。验证严格时间、数量和区域合法性。
4. Python 校验 setting、region_at；FFmpeg按时间生成遮罩，跨帧变化排除参与比较帧各自忽略区域的并集；分组OCR按当前帧过滤，图像比较使用相应帧遮罩交集。原截图/OCR不裁剪。
5. 测试真实短视频的框位置切换、正常课件变化、截图原始数据、前后端传参、浏览器框选/移动/缩放/时间切换/同点覆盖/持久化。构建与相关完整回归后检查空闲再更新本地服务，无付费模型调用。
''',encoding='utf-8')
(root/'desktop/src/videoRegionTimeline.test.mjs').write_text('''import test from 'node:test'
import assert from 'node:assert/strict'
import {normalizeIgnoreSetting, regionAt, upsertRegionNode, removeRegionNode, regionNodes} from './videoRegionTimeline.ts'
const a={x:.7,y:.6,width:.2,height:.3},b={x:.1,y:.1,width:.2,height:.2}
test('first edit starts at zero even when drawn later',()=>{const t=upsertRegionNode(null,5000,a);assert.equal(regionNodes(t)[0].timeMs,0);assert.deepEqual(regionAt(t,0),a);assert.deepEqual(regionAt(t,9000),a)})
test('subsequent edits switch at exact boundaries and replace same timestamp',()=>{let t=upsertRegionNode(a,5000,b);assert.deepEqual(regionAt(t,4999),a);assert.deepEqual(regionAt(t,5000),b);t=upsertRegionNode(t,5000,a);assert.equal(regionNodes(t).length,2);assert.deepEqual(regionAt(t,5000),a)})
test('deleting a later node restores previous segment and preserves zero baseline',()=>{let t=upsertRegionNode(a,5000,b);t=removeRegionNode(t,5000);assert.deepEqual(regionAt(t,9000),a);assert.equal(regionNodes(removeRegionNode(t,0)).length,1)})
test('invalid timelines cannot silently turn into a static region',()=>{for(const v of [{nodes:[]},{nodes:[{timeMs:2,region:a}]},{nodes:[{timeMs:0,region:a},{timeMs:0,region:b}]},{nodes:[{timeMs:0,region:a},{timeMs:NaN,region:b}]}])assert.equal(normalizeIgnoreSetting(v),null);assert.deepEqual(normalizeIgnoreSetting(a),a)})
''',encoding='utf-8')
(root/'agent-python/test_region_timeline.py').write_text('''import unittest
from ignored_region import normalize_setting, region_at
from app import TranscribeRequest
A=dict(x=.7,y=.6,width=.2,height=.3)
B=dict(x=.1,y=.1,width=.2,height=.2)
TIMELINE={'nodes':[{'timeMs':0,'region':A},{'timeMs':5000,'region':B}]}
class TimelineTest(unittest.TestCase):
 def test_boundaries_and_static_compatibility(self):
  self.assertEqual(region_at(normalize_setting(TIMELINE),4999),A)
  self.assertEqual(region_at(TIMELINE,5000),B)
  self.assertEqual(region_at(A,99000),A)
  self.assertEqual(TranscribeRequest(fileId='fixture',ignoredRegion=TIMELINE).ignoredRegion,TIMELINE)
 def test_rejects_invalid_timeline(self):
  for v in [{'nodes':[]},{'nodes':[{'timeMs':1,'region':A}]},{'nodes':[{'timeMs':0,'region':A},{'timeMs':0,'region':B}]},{'nodes':[{'timeMs':0,'region':A},{'timeMs':True,'region':B}]},{'nodes':[{'timeMs':0,'region':A},{'timeMs':5000,'region':{'nodes':[]}}]}]:
   with self.subTest(value=v),self.assertRaises(ValueError):normalize_setting(v)
 def test_disabled_segment(self):
  self.assertIsNone(region_at({'nodes':[{'timeMs':0,'region':A},{'timeMs':5000,'region':None}]},5000))
''',encoding='utf-8')
(root/'backend-java/src/test/java/cn/videostudy/api/IgnoreRegionTimelineTest.java').write_text('''package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;
import static org.junit.jupiter.api.Assertions.*;
class IgnoreRegionTimelineTest {
 String a="{\\"x\\":0.7,\\"y\\":0.6,\\"width\\":0.2,\\"height\\":0.3}";
 @Test void parsesAndRoundTripsStaticAndTimeline() throws Exception {
  String json="{\\"nodes\\":[{\\"timeMs\\":0,\\"region\\":"+a+"},{\\"timeMs\\":5000,\\"region\\":null}]}";
  var parsed=IgnoreRegion.parse(json);
  var encoded=new ObjectMapper().writeValueAsString(parsed);
  assertEquals(parsed,IgnoreRegion.parse(encoded));
  assertTrue(encoded.contains("5000"));
  assertEquals(4,new ObjectMapper().readTree(new ObjectMapper().writeValueAsString(IgnoreRegion.parse(a))).size());
 }
 @Test void rejectsInvalidTimelineBoundaries() {
  for(String json:new String[]{"{\\"nodes\\":[]}","{\\"nodes\\":[{\\"timeMs\\":1,\\"region\\":"+a+"}]}","{\\"nodes\\":[{\\"timeMs\\":0,\\"region\\":"+a+"},{\\"timeMs\\":0,\\"region\\":null}]}","{\\"nodes\\":[{\\"timeMs\\":0,\\"region\\":"+a+"},{\\"timeMs\\":0.5,\\"region\\":null}]}"})assertThrows(IllegalArgumentException.class,()->IgnoreRegion.parse(json));
 }
}
''',encoding='utf-8')
