"""Audit saved paired GPU outputs against manually inspected original slide facts.
No model/API calls. Slide consistency is not audio transcription accuracy.
"""
from datetime import datetime,timezone
from pathlib import Path
import difflib,json,re,statistics,time
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'.local/qa/batch4-benchmark-20261013T162340Z'
FRAME_DIR=ROOT/'.local/keyframes/56ac6493-3085-45e2-b9c4-130b583b95d1'
OUT=ROOT/'.local/qa'/('batch4-quality-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));OUT.mkdir(parents=True)
start=time.monotonic()
a=json.loads((SOURCE/'standard-alone-transcript.json').read_text(encoding='utf-8'))
b=json.loads((SOURCE/'batch4-alone-transcript.json').read_text(encoding='utf-8'))
bench=json.loads((SOURCE/'results.json').read_text(encoding='utf-8'))
def norm(text):return ''.join(re.findall(r'[\w]',text.lower()))
def summary(rows):
 durations=[s['end']-s['start'] for s in rows]
 return {'segments':len(rows),'characters':sum(len(s['text']) for s in rows),'medianSegmentSeconds':round(statistics.median(durations),3),'maxSegmentSeconds':round(max(durations),3),'invalidTimes':sum(s['start']<0 or s['end']<s['start'] for s in rows),'outOfOrder':sum(s['start']<p['start'] for p,s in zip(rows,rows[1:]))}
def excerpt(rows,lo,hi):return [{'start':s['start'],'end':s['end'],'text':s['text']} for s in rows if (lo<=(s['start']+s['end'])/2<hi)]
# Review annotations come from original images inspected by the assistant, not OCR.
# Windows are diagnostic samples selected from differences; do not calculate a global accuracy percentage.
checks=[
 (1826,1829,'1839000.jpg','极限非零，分子趋于0时，分母也趋于0。','普通结果更符合画面','batch4把关键数值0写成6。'),
 (2547,2550,'2568000.jpg','分段条件的比较界限为x<1。','batch4更符合画面','普通写成x小于e；batch4写成挨个子小于1，数值正确但变量写法错误。'),
 (2550,2552,'2568000.jpg','x<1时结果为0。','batch4更符合画面','普通写成结果未定；batch4写成结果为0。'),
 (2552,2554,'2568000.jpg','x=1时结果为-e/2。','两者均未完整保留','两者的相应片段都只写了负二分之一，未体现图中的因子e；未经听音，不能确定是转写遗漏还是老师口头省略。'),
 (1799,1803,'1800000.jpg','第9题系数a=-1/12。','两者均保留主要数值','普通使用副等同音字，batch4使用负，但二者都出现周边识别错误。'),
 (1802.9,1804.1,'1800000.jpg','第9题指数b=6。','两者均符合画面','二者均写出b为6。'),
 (2411,2414,'2397000.jpg','所用方法是等价无穷小，e^u-1与u等价。','batch4术语写法更好','普通写成等价五穷小；batch4写成等价无穷小；不代表整段公式都识别正确。'),
 (1500,1527,'1512000.jpg','第7题结论为同阶但非等价无穷小。','两者均保留主要结论','二者都出现同阶和非等价，周边无穷小等词仍有错误。'),
]
review=[]
for lo,hi,frame,expected,verdict,note in checks:
 assert (FRAME_DIR/frame).is_file()
 review.append({'start':lo,'end':hi,'originalFrame':str((FRAME_DIR/frame).resolve()),'expectedSlideFact':expected,'standard':excerpt(a,lo,hi),'batch4':excerpt(b,lo,hi),'verdict':verdict,'note':note})
x=norm(''.join(s['text'] for s in a));y=norm(''.join(s['text'] for s in b))
similarity=difflib.SequenceMatcher(None,x,y,autojunk=False).ratio()
windows=[]
for lo in range(0,2613,30):
 xw=norm(''.join(s['text'] for s in excerpt(a,lo,lo+30)));yw=norm(''.join(s['text'] for s in excerpt(b,lo,lo+30)))
 windows.append({'start':lo,'end':min(lo+30,2612.928),'standardCharacters':len(xw),'batch4Characters':len(yw),'agreement':round(difflib.SequenceMatcher(None,xw,yw,autojunk=False).ratio(),4)})
report={'mode':'reuse_existing_measured_outputs_and_original_slide_review','freshInference':False,'paidModelCalls':0,'durationSeconds':bench['audio_duration_s'],'model':'small','device':'cuda','batchSize':4,'segmentTimestamps':True,'standard':summary(a),'batch4':summary(b),'normalizedTextAgreement':round(similarity,4),'characterErrorRate':None,'wordErrorRate':None,'humanAudioGroundTruth':False,'reviews':review,'diagnosticWindows':windows,'limitations':['画面事实不是逐字音频真值，不能计算CER/WER。','样本按差异选择，不是随机样本，不能推断整体准确率。','普通方式和批量方式的处理路径不同，不能把所有差异归因于batch_size=4。','当前Docker服务不可用，未能追加batch1与batch4的相同处理路径对照。']}
(OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# small 普通转写与 batch4 质量核对','',f'使用此前同一43分33秒课程的GPU实测输出；本次没有重新调用模型。文字一致率为{similarity:.1%}，它不是准确率，也不能把剩余比例当成错误率。','', '| 时间 | 原图事实 | 核对发现 |','|---|---|---|']
for row in review:
 label=f"{int(row['start'])//60:02d}:{int(row['start'])%60:02d}"
 lines.append(f"| {label} | {row['expectedSlideFact']} | {row['verdict']}：{row['note']} |")
lines+=['','## 判断','batch4并非单方面降低质量：存在改善，也存在关键数字错误；普通方式同样存在错误。本课程不宜把任一种转写直接当成公式和条件的最终依据。','建议继续以原图核对公式、数值和条件；纯口头补充必须结合音频人工抽查。此次不改变正式配置。','','## 测试边界',*['- '+s for s in report['limitations']],'','分段时间合法不代表与原音完全准确对齐。尚未逐字听音标注，未计算准确率。']
(OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(OUT/'events.jsonl').write_text(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'operation':'transcription_quality_audit','status':'completed','elapsed_ms':round((time.monotonic()-start)*1000),'review_count':len(review),'fresh_inference':False,'paid_model_calls':0})+'\n',encoding='utf-8')
print(json.dumps({'output':str(OUT),'standard':report['standard'],'batch4':report['batch4'],'textAgreement':report['normalizedTextAgreement'],'reviewCount':len(review),'accuracyMeasured':False},ensure_ascii=False))
