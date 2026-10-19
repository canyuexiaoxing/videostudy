"""Bounded mathematical diagrams. Model supplies data, never executable SVG or code."""
import ast,math,re

def number(value):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value)>1e12:raise ValueError('invalid_diagram_number')
 return float(value)
def text(value,limit=80):
 if not isinstance(value,str) or len(value)>limit:raise ValueError('invalid_diagram_text')
 return value.strip()
def same(a,b):return math.isclose(a,b,rel_tol=1e-6,abs_tol=.005)
def identifier(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,15}',value):raise ValueError('invalid_diagram_id')
 return value
FUNCTIONS={k:getattr(math,k) for k in ('sin','cos','tan','sqrt','log','log10','exp','asin','acos','atan')}
FUNCTIONS.update(abs=abs,ln=math.log)
def expression_function(source,variable=True):
 if not isinstance(source,str) or not source or len(source)>160:raise ValueError('invalid_function_expression')
 try:tree=ast.parse(source.replace('^','**').replace('π','pi'),mode='eval')
 except (SyntaxError,ValueError):raise ValueError('invalid_function_expression') from None
 if sum(1 for _ in ast.walk(tree))>70:raise ValueError('function_expression_too_complex')
 def validate(n):
  if isinstance(n,ast.Constant):number(n.value)
  elif isinstance(n,ast.Name) and n.id in (('x','pi','e') if variable else ('pi','e')):pass
  elif isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):validate(n.operand)
  elif isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):validate(n.left);validate(n.right)
  elif isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in FUNCTIONS and len(n.args)==1 and not n.keywords:validate(n.args[0])
  else:raise ValueError('unsupported_function_expression')
 validate(tree.body)
 def evaluate(x=0,root=tree.body):
  def visit(n):
   if isinstance(n,ast.Constant):return number(n.value)
   if isinstance(n,ast.Name):return x if n.id=='x' else math.pi if n.id=='pi' else math.e
   if isinstance(n,ast.UnaryOp):return number(visit(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1))
   if isinstance(n,ast.Call):return number(FUNCTIONS[n.func.id](visit(n.args[0])))
   a,b=visit(n.left),visit(n.right)
   if isinstance(n.op,ast.Add):value=a+b
   elif isinstance(n.op,ast.Sub):value=a-b
   elif isinstance(n.op,ast.Mult):value=a*b
   elif isinstance(n.op,ast.Div):value=a/b
   else:
    if abs(b)>20:raise ValueError('exponent_too_large')
    value=math.pow(a,b)
   return number(value)
  try:return visit(root)
  except (ValueError,TypeError,OverflowError,ZeroDivisionError):raise ValueError('function_undefined') from None
 critical=[]
 for node in ast.walk(tree):
  if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):critical.append((node.right,False))
  if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='tan':critical.append((node.args[0],True))
  if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Pow):
   try:
    if ast.literal_eval(node.right)<0:critical.append((node.left,False))
   except (ValueError,TypeError):pass
 def crosses(a,b):
  for root,tangent in critical:
   try:
    left,right=evaluate(a,root),evaluate(b,root)
    if tangent:left,right=math.cos(left),math.cos(right)
    if left*right<=0:return True
   except ValueError:return True
  return False
 evaluate.crosses=crosses
 return evaluate

def numeric_option(source):
 source=source.strip()
 for a,b in (('\\(','\\)'),('\\[','\\]'),('$$','$$'),('$','$')):
  if source.startswith(a) and source.endswith(b):source=source[len(a):-len(b)].strip();break
 source=re.sub(r'\\(?:mathrm|text)\{[^{}]*\}','',source)
 for _ in range(8):
  previous=source
  source=re.sub(r'\\(?:dfrac|tfrac|frac)\{([^{}]+)\}\{([^{}]+)\}',r'((\1)/(\2))',source)
  source=re.sub(r'\\sqrt\{([^{}]+)\}',r'sqrt(\1)',source)
  if source==previous:break
 source=source.replace(r'\left','').replace(r'\right','')
 source=re.sub(r'\^\{([^{}]+)\}',r'**(\1)',source)
 for a,b in ((r'\times','*'),(r'\cdot','*'),(r'\pi','pi'),(r'\%','%'),(r'\,',''),(r'\!',''),(r'\;','')):source=source.replace(a,b)
 source=re.sub(r'\s*(?:%|Ω|°|℃|cm|mm|km|m|ms|s|kg|g|N|J|W|Pa|Hz|V|A|rad|度|厘米|米|斤|件|万件|元)\s*$','',source)
 return expression_function(source,variable=False)()

def _range(raw):
 if not isinstance(raw,list) or len(raw)!=2:raise ValueError('invalid_function_range')
 a,b=map(number,raw)
 if not -1e6<=a<b<=1e6 or b-a<1e-6:raise ValueError('invalid_function_range')
 return [a,b]
def _answer(expected,answer):
 if answer is None or not same(number(expected),number(answer)):raise ValueError('diagram_answer_mismatch')
def _function(raw,answer):
 domain=_range(raw.get('domain'));view=_range(raw.get('range'));curves=raw.get('curves')
 if not isinstance(curves,list) or not 1<=len(curves)<=3:raise ValueError('invalid_function_curves')
 output=[];functions=[]
 for curve in curves:
  if not isinstance(curve,dict):raise ValueError('invalid_function_curve')
  f=expression_function(curve.get('expression'));functions.append(f);segments=[];segment=[];last=None
  for i in range(601):
   x=domain[0]+(domain[1]-domain[0])*i/600
   try:
    y=f(x)
    if not view[0]<=y<=view[1]:raise ValueError('outside_view')
    if last is not None and (abs(y-last)>(view[1]-view[0])*.35 or f.crosses(segment[-1][0],x)):
     if len(segment)>1:segments.append(segment)
     segment=[]
    segment.append([x,y]);last=y
   except ValueError:
    if len(segment)>1:segments.append(segment)
    segment=[];last=None
  if len(segment)>1:segments.append(segment)
  if not segments:raise ValueError('function_not_visible')
  # Sub-sample visible segments to reject severely under-resolved oscillations.
  for visible in segments:
   for a,b in zip(visible,visible[1:]):
    for fraction in (.25,.5,.75):
     try:middle=f(a[0]+(b[0]-a[0])*fraction)
     except ValueError:raise ValueError('function_sampling_too_coarse') from None
     linear=a[1]+(b[1]-a[1])*fraction
     if abs(middle-linear)>(view[1]-view[0])*.03:raise ValueError('function_sampling_too_coarse')
  output.append({'label':text(curve.get('label','f'),30),'segments':segments})
 if answer is not None:
  check=raw.get('check',{});index=check.get('curveIndex',0);x=number(check.get('x'))
  if check.get('operation')!='value_at' or type(index) is not int or not 0<=index<len(functions) or not domain[0]<=x<=domain[1]:raise ValueError('invalid_function_check')
  _answer(functions[index](x),answer)
 return {'kind':'function','title':text(raw.get('title','函数图')),'domain':domain,'range':view,'curves':output}

def _points(raw,minimum=1,maximum=20):
 if not isinstance(raw,list) or not minimum<=len(raw)<=maximum:raise ValueError('invalid_diagram_points')
 points={};positions=set()
 for p in raw:
  if not isinstance(p,dict):raise ValueError('invalid_diagram_point')
  identity=identifier(p.get('id'));x,y=number(p.get('x')),number(p.get('y'))
  if abs(x)>1e6 or abs(y)>1e6 or identity in points or (x,y) in positions:raise ValueError('duplicate_or_large_point')
  points[identity]={'id':identity,'x':x,'y':y,'label':text(p.get('label',identity),30)};positions.add((x,y))
 return points

def _edge(edge,points):
 if not isinstance(edge,dict) or edge.get('from') not in points or edge.get('to') not in points or edge['from']==edge['to']:raise ValueError('invalid_diagram_edge')
 return {'from':edge['from'],'to':edge['to']}
def _geometry(raw,answer):
 points=_points(raw.get('points'));edges=raw.get('edges',[]);circles=raw.get('circles',[]);angles=raw.get('angles',[])
 if not isinstance(edges,list) or len(edges)>40 or not isinstance(circles,list) or len(circles)>8 or not isinstance(angles,list) or len(angles)>12:raise ValueError('geometry_too_complex')
 out=[]
 for edge in edges:
  e=_edge(edge,points);e['dashed']=edge.get('dashed') is True;e['arrow']=edge.get('arrow') is True;e['label']=text(edge.get('label',''),30)
  numeric=re.fullmatch(r'([-+]?\d+(?:\.\d+)?)(?:\s*[A-Za-z厘米米]*)',e['label'])
  if numeric:
   a,b=points[e['from']],points[e['to']]
   if not same(float(numeric[1]),math.hypot(a['x']-b['x'],a['y']-b['y'])):raise ValueError('geometry_label_mismatch')
  out.append(e)
 rounds=[]
 for circle in circles:
  if not isinstance(circle,dict) or circle.get('center') not in points:raise ValueError('invalid_circle')
  radius=number(circle.get('radius'))
  if not 0<radius<=1e6:raise ValueError('invalid_circle')
  rounds.append({'center':circle['center'],'radius':radius})
 marks=[]
 for angle in angles:
  if not isinstance(angle,dict) or len({angle.get(k) for k in ('a','vertex','b')})!=3 or any(angle.get(k) not in points for k in ('a','vertex','b')):raise ValueError('invalid_geometry_angle')
  marks.append({**{k:angle[k] for k in ('a','vertex','b')},'label':text(angle.get('label',''),30)})
 if not out and not rounds:raise ValueError('empty_geometry')
 if answer is not None:
  check=raw.get('check',{});operation=check.get('operation')
  try:
   if operation=='distance':
    a,b=points[check['from']],points[check['to']];expected=math.hypot(a['x']-b['x'],a['y']-b['y'])
   elif operation=='triangle_area':
    a,b,c=[points[check[k]] for k in ('a','b','c')];expected=abs((b['x']-a['x'])*(c['y']-a['y'])-(b['y']-a['y'])*(c['x']-a['x']))/2
    if expected<1e-10:raise ValueError('degenerate_triangle')
   elif operation=='angle':
    a,v,b=[points[check[k]] for k in ('a','vertex','b')];u=(a['x']-v['x'],a['y']-v['y']);w=(b['x']-v['x'],b['y']-v['y']);expected=math.degrees(math.acos(max(-1,min(1,(u[0]*w[0]+u[1]*w[1])/(math.hypot(*u)*math.hypot(*w))))))
   else:raise ValueError('unsupported_geometry_check')
  except (KeyError,ZeroDivisionError):raise ValueError('invalid_geometry_check') from None
  _answer(expected,answer)
 return {'kind':'geometry','title':text(raw.get('title','几何图')),'points':list(points.values()),'edges':out,'circles':rounds,'angles':marks}

def _solve(matrix,values):
 size=len(values);a=[list(row)+[value] for row,value in zip(matrix,values)]
 for i in range(size):
  pivot=max(range(i,size),key=lambda j:abs(a[j][i]))
  if abs(a[pivot][i])<1e-12:raise ValueError('circuit_underdetermined')
  a[i],a[pivot]=a[pivot],a[i];scale=a[i][i];a[i]=[x/scale for x in a[i]]
  for j in range(size):
   if j!=i:
    factor=a[j][i];a[j]=[x-factor*y for x,y in zip(a[j],a[i])]
 return [row[-1] for row in a]
def _circuit_answer(nodes,components,wires,check):
 parent={n:n for n in nodes}
 def find(n):
  while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
  return n
 def join(a,b):parent[find(a)]=find(b)
 for wire in wires:join(wire['from'],wire['to'])
 for c in components:
  if c['type']=='ammeter' or c['type']=='switch' and c['closed']:join(c['from'],c['to'])
 batteries=[c for c in components if c['type']=='battery']
 if len(batteries)!=1 or any(c['type'] in ('capacitor','inductor') for c in components):raise ValueError('unsupported_circuit_calculation')
 battery=batteries[0];positive,negative=find(battery['from']),find(battery['to'])
 if positive==negative:raise ValueError('shorted_battery')
 resistors=[c for c in components if c['type'] in ('resistor','lamp')];neighbors={find(n):set() for n in nodes}
 for c in resistors:a,b=find(c['from']),find(c['to']);neighbors[a].add(b);neighbors[b].add(a)
 reachable={positive,negative};pending=list(reachable)
 while pending:
  n=pending.pop()
  for neighbor in neighbors[n]-reachable:reachable.add(neighbor);pending.append(neighbor)
 unknown=sorted(reachable-{positive,negative});positions={n:i for i,n in enumerate(unknown)};voltage={positive:battery['value'],negative:0};matrix=[[0.0]*len(unknown) for _ in unknown];values=[0.0]*len(unknown)
 for c in resistors:
  a,b=find(c['from']),find(c['to'])
  if a==b:continue
  conductance=1/c['value']
  for node,other in ((a,b),(b,a)):
   if node in positions:
    i=positions[node];matrix[i][i]+=conductance
    if other in positions:matrix[i][positions[other]]-=conductance
    else:values[i]+=conductance*voltage.get(other,0)
 voltage.update(zip(unknown,_solve(matrix,values)))
 operation=check.get('operation')
 if operation=='total_current':
  total=0
  for c in resistors:
   a,b=find(c['from']),find(c['to'])
   if a==positive:total+=(voltage[positive]-voltage.get(b,voltage[positive]))/c['value']
   elif b==positive:total+=(voltage[positive]-voltage.get(a,voltage[positive]))/c['value']
  return abs(total)
 target=next((c for c in resistors if c['id']==check.get('componentId')),None)
 if not target or operation not in ('resistor_current','resistor_voltage'):raise ValueError('invalid_circuit_check')
 a,b=find(target['from']),find(target['to'])
 if a not in voltage or b not in voltage:raise ValueError('floating_circuit_target')
 difference=abs(voltage[a]-voltage[b]);return difference/target['value'] if operation=='resistor_current' else difference

def _circuit(raw,answer):
 nodes=_points(raw.get('nodes'),2,24);components=raw.get('components');wires=raw.get('wires',[])
 if not isinstance(components,list) or not 1<=len(components)<=16 or not isinstance(wires,list) or len(wires)>32:raise ValueError('invalid_circuit_components')
 output=[];ids=set();units={'battery':'V','resistor':'Ω','lamp':'Ω','capacitor':'F','inductor':'H','switch':'','ammeter':'','voltmeter':''}
 for c in components:
  e=_edge(c,nodes);identity=identifier(c.get('id'));kind=c.get('type')
  if identity in ids or kind not in units:raise ValueError('invalid_circuit_component')
  ids.add(identity);e.update(id=identity,type=kind)
  if kind in ('battery','resistor','lamp','capacitor','inductor'):
   value=number(c.get('value'))
   if not 1e-9<=value<=1e9:raise ValueError('invalid_circuit_value')
   e.update(value=value,unit=units[kind])
  if kind=='switch':
   if type(c.get('closed')) is not bool:raise ValueError('invalid_switch_state')
   e['closed']=c['closed']
  output.append(e)
 clean_wires=[_edge(w,nodes) for w in wires]
 # A crossing with no explicit shared node is ambiguous in an automatically generated schematic.
 all_edges=output+clean_wires
 for i,e in enumerate(all_edges):
  a,b=nodes[e['from']],nodes[e['to']]
  if math.hypot(a['x']-b['x'],a['y']-b['y'])<.01:raise ValueError('circuit_component_too_short')
  for f in all_edges[i+1:]:
   if {e['from'],e['to']}=={f['from'],f['to']}:raise ValueError('overlapping_circuit_edges')
   common={e['from'],e['to']}&{f['from'],f['to']}
   if common:
    shared=next(iter(common));origin=nodes[shared];one=nodes[e['to'] if e['from']==shared else e['from']];two=nodes[f['to'] if f['from']==shared else f['from']]
    ux,uy=one['x']-origin['x'],one['y']-origin['y'];vx,vy=two['x']-origin['x'],two['y']-origin['y']
    if abs(ux*vy-uy*vx)<1e-10 and ux*vx+uy*vy>0:raise ValueError('overlapping_circuit_edges')
    continue
   c,d=nodes[f['from']],nodes[f['to']]
   def cross(p,q,r):return (q['x']-p['x'])*(r['y']-p['y'])-(q['y']-p['y'])*(r['x']-p['x'])
   if max(min(a['x'],b['x']),min(c['x'],d['x']))<=min(max(a['x'],b['x']),max(c['x'],d['x'])) and max(min(a['y'],b['y']),min(c['y'],d['y']))<=min(max(a['y'],b['y']),max(c['y'],d['y'])) and cross(a,b,c)*cross(a,b,d)<=0 and cross(c,d,a)*cross(c,d,b)<=0:raise ValueError('ambiguous_circuit_crossing')
 if answer is not None:_answer(_circuit_answer(nodes,output,clean_wires,raw.get('check',{})),answer)
 return {'kind':'circuit','title':text(raw.get('title','电路图')),'nodes':list(nodes.values()),'components':output,'wires':clean_wires}

def _chart(raw,answer):
 kind=raw['kind'];values=raw.get('values');scatter=kind=='scatter'
 if not isinstance(values,list) or not 2<=len(values)<=(10 if kind=='pie' else 20):raise ValueError('invalid_chart_values')
 clean=[];labels=set()
 for i,item in enumerate(values):
  if not isinstance(item,dict):raise ValueError('invalid_chart_values')
  label=text(item.get('label',str(i+1)),40)
  if label in labels:raise ValueError('duplicate_chart_label')
  labels.add(label)
  clean.append({'label':label,'x':number(item.get('x')),'y':number(item.get('y'))} if scatter else {'label':label,'value':number(item.get('value'))})
 if kind=='pie' and (any(v['value']<0 for v in clean) or sum(v['value'] for v in clean)<=0):raise ValueError('invalid_pie_values')
 if answer is not None:
  check=raw.get('check',{});a,b=check.get('fromIndex'),check.get('toIndex');operation=check.get('operation')
  if type(b) is not int or not 0<=b<len(clean):raise ValueError('invalid_chart_check')
  last=clean[b]['y' if scatter else 'value']
  if operation=='read_value':expected=last
  elif operation=='share' and kind=='pie':expected=last/sum(v['value'] for v in clean)*100
  else:
   if type(a) is not int or not 0<=a<len(clean):raise ValueError('invalid_chart_check')
   first=clean[a]['y' if scatter else 'value']
   try:
    if operation=='difference':expected=last-first
    elif operation=='growth_rate':expected=(last-first)/first*100
    elif operation=='slope' and scatter:expected=(last-first)/(clean[b]['x']-clean[a]['x'])
    else:raise ValueError('unsupported_chart_check')
   except ZeroDivisionError:raise ValueError('undefined_chart_check') from None
  _answer(expected,answer)
 return {'kind':kind,'title':text(raw.get('title','图表')),'unit':text(raw.get('unit',''),30),'values':clean}

def validate_structured_diagram(raw,answer):
 if not isinstance(raw,dict):raise ValueError('invalid_diagram')
 try:
  kind=raw.get('kind')
  if kind=='function':return _function(raw,answer)
  if kind=='geometry':return _geometry(raw,answer)
  if kind=='circuit' and 'nodes' in raw:return _circuit(raw,answer)
  if kind in ('bar','line','table','pie','scatter'):return _chart(raw,answer)
 except (KeyError,TypeError,AttributeError,IndexError,OverflowError,ZeroDivisionError):raise ValueError('invalid_diagram') from None
 raise ValueError('unsupported_diagram')
