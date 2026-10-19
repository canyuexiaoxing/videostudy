"""Generate deterministic accepted questions for UI verification, no model calls."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'agent-python'))
from practice import validate_question
nodes=[{'id':'n1','title':'公式与图形测试','evidenceRefs':[{'sourceId':'s1','startMs':0,'endMs':10000,'quote':'测试课程依据'}]}]
questions=[]
def add(title,diagram,prompt=r'根据图示，判断正确说法。已知 \(a=\frac{1}{2}\)。',value=None,expression=None,options=None):
 options=options or (['1','2','3','4'] if value is not None else [r'\(\frac{1}{2}\)',r'\(\sqrt{2}\)',r'\(x^2\)',r'\(\int_0^1x\,dx\)'])
 index=0 if value is None else next(i for i,option in enumerate(options) if float(option.strip('$').strip())==value)
 raw={'nodeId':'n1','sourceIds':['s1'],'kind':'single','task':'concept' if value is None else 'calculation','title':title,'prompt':prompt,'options':options,'answerIndex':index,'explanation':r'使用老师的方法：\[\frac{a+b}{2}=\sqrt{x^2+1}\] 再代入条件。','distractorReasons':['' if i==index else r'注意分母 \(b\neq0\)。' for i in range(4)],'takeaway':r'注意 \(\Delta y/\Delta x\) 的含义。','scenario':'adapted','diagram':diagram,'calculation':None if value is None else {'expression':expression or str(value),'value':value,'optionValues':[float(o) for o in options]}}
 questions.append(validate_question(raw,nodes))
for kind in ['bar','line','table']:add(kind,{'kind':kind,'title':'正负数据比较','unit':'单位','values':[{'label':'项目甲','value':-2},{'label':'项目乙','value':4},{'label':'项目丙','value':1}]})
add('pie',{'kind':'pie','title':'各类数量','unit':'个','values':[{'label':'甲类','value':2},{'label':'乙类','value':3}]})
add('scatter',{'kind':'scatter','title':'观测散点','values':[{'label':'A','x':-2,'y':-1},{'label':'B','x':1,'y':3},{'label':'C','x':3,'y':1}]})
add('function',{'kind':'function','title':r'函数 \(f\) 与 \(g\)','domain':[-3,3],'range':[-2,10],'curves':[{'label':'f','expression':'x**2'},{'label':'g','expression':'sin(x)'}]})
add('function-pole',{'kind':'function','title':r'函数 \(h\)','domain':[-3,3],'range':[-5,5],'curves':[{'label':'h','expression':'1/x'}]})
add('geometry',{'kind':'geometry','title':'三角形 ABC','points':[{'id':'A','x':0,'y':0},{'id':'B','x':4,'y':0},{'id':'C','x':0,'y':3}],'edges':[{'from':'A','to':'B','label':'4'},{'from':'A','to':'C','label':'3'},{'from':'B','to':'C','label':'a'}],'angles':[{'a':'B','vertex':'A','b':'C','label':'θ'}],'check':{'operation':'distance','from':'B','to':'C'}},r'求图中 \(a=|BC|\) 的长度。',5,options=['2','3','4','5'])
add('circle',{'kind':'geometry','title':'圆与两条半径','points':[{'id':'O','x':0,'y':0},{'id':'A','x':2,'y':0},{'id':'B','x':0,'y':2}],'edges':[{'from':'O','to':'A','arrow':True},{'from':'O','to':'B','dashed':True}],'circles':[{'center':'O','radius':2}],'angles':[{'a':'A','vertex':'O','b':'B','label':'α'}]})
add('circuit',{'kind':'circuit','title':'并联电阻电路','nodes':[{'id':'p','x':0,'y':0},{'id':'a','x':3,'y':0},{'id':'n','x':0,'y':3},{'id':'b','x':3,'y':3},{'id':'c','x':5,'y':0},{'id':'d','x':5,'y':3}], 'components':[{'id':'V','type':'battery','from':'p','to':'n','value':12},{'id':'R1','type':'resistor','from':'a','to':'b','value':6},{'id':'R2','type':'resistor','from':'c','to':'d','value':3}], 'wires':[{'from':'p','to':'a'},{'from':'a','to':'c'},{'from':'n','to':'b'},{'from':'b','to':'d'}],'check':{'operation':'total_current'}},r'电源电压为 \(12\,\mathrm{V}\)，求总电流。',6,'12/6+12/3',['2','3','4','6'])
add('legacy-circuit',{'kind':'circuit','topology':'r1_series_r2_parallel_r3','voltage':12,'r1':2,'r2':3,'r3':6,'target':'total_current'},'求总电流。',3,'12/(2+3*6/(3+6))',['1','2','3','6'])
add('circuit-components',{'kind':'circuit','title':'电容电感示意电路','nodes':[{'id':'p','x':0,'y':0},{'id':'a','x':4,'y':0},{'id':'b','x':4,'y':3},{'id':'n','x':0,'y':3}],'components':[{'id':'V','type':'battery','from':'p','to':'n','value':6},{'id':'C','type':'capacitor','from':'p','to':'a','value':.001},{'id':'L','type':'inductor','from':'a','to':'b','value':.01},{'id':'S','type':'switch','from':'b','to':'n','closed':False}],'wires':[]})
symbol_nodes=[{'id':f'n{i}','x':x,'y':y} for i,(x,y) in enumerate([(0,0),(3,0),(6,0),(9,0),(9,3),(6,3),(3,3),(0,3)])]
symbol_types=['battery','resistor','lamp','capacitor','inductor','switch','ammeter','voltmeter']
symbol_components=[]
for i,kind in enumerate(symbol_types):
 c={'id':f'K{i}','type':kind,'from':f'n{i}','to':f'n{(i+1)%8}'}
 if kind in ('battery','resistor','lamp','capacitor','inductor'):c['value']=6 if kind not in ('capacitor','inductor') else .001
 if kind=='switch':c['closed']=True
 symbol_components.append(c)
add('circuit-symbols',{'kind':'circuit','title':'常见电路元件示意','nodes':symbol_nodes,'components':symbol_components,'wires':[]})
add('latex-matrix',None,r'考虑矩阵 \[A=\begin{pmatrix}1&2\\3&4\end{pmatrix}\] 以及 \(\sum_{n=1}^{\infty}\frac{1}{n^2}\)，选择正确描述。')
add('latex-fallback',None,r'未知命令应保留原文：\(\unknowncommand{x}\)。')
add('latex-long',None,r'长公式可横向滚动：\['+'+'.join(f'x_{{{i}}}' for i in range(80))+r'\]')
out=ROOT/'.local/qa/math-figures';out.mkdir(parents=True,exist_ok=True);(out/'fixtures.json').write_text(json.dumps(questions,ensure_ascii=False),encoding='utf8');print(json.dumps({'acceptedQuestions':len(questions),'paidModelCalls':0}))
