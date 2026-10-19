import unittest,math
from practice_diagrams import validate_structured_diagram
class StructuredDiagramTests(unittest.TestCase):
 def test_function_is_sampled_without_executing_code_or_crossing_pole(self):
  graph={'kind':'function','title':'函数图','domain':[-3,3],'range':[-5,5],'curves':[{'label':'f','expression':'1/x'}]}
  result=validate_structured_diagram(graph,None);self.assertGreaterEqual(len(result['curves'][0]['segments']),2)
  for segment in result['curves'][0]['segments']:self.assertFalse(any(a[0]<0<b[0] for a,b in zip(segment,segment[1:])))
  graph['curves'][0]['expression']='__import__("os").system("bad")'
  with self.assertRaises(ValueError):validate_structured_diagram(graph,None)
 def test_unsampled_shifted_pole_and_tangent_are_split(self):
  for expression,pole in [('1/(x-0.003)',.003),('tan(x)',math.pi/2)]:
   graph={'kind':'function','domain':[-1,3],'range':[-100000,100000],'curves':[{'expression':expression}]}
   result=validate_structured_diagram(graph,None)
   for segment in result['curves'][0]['segments']:
    self.assertFalse(any(a[0]<pole<b[0] for a,b in zip(segment,segment[1:])))
 def test_function_numeric_answer_checked(self):
  graph={'kind':'function','domain':[-2,2],'range':[-1,5],'curves':[{'expression':'x**2'}],'check':{'operation':'value_at','curveIndex':0,'x':2}}
  self.assertTrue(validate_structured_diagram(graph,4))
  with self.assertRaises(ValueError):validate_structured_diagram(graph,3)
 def test_geometry_coordinates_determine_length_and_reject_unknown_points(self):
  diagram={'kind':'geometry','points':[{'id':'A','x':0,'y':0},{'id':'B','x':3,'y':0},{'id':'C','x':0,'y':4}],'edges':[{'from':'B','to':'C'}],'check':{'operation':'distance','from':'B','to':'C'}}
  result=validate_structured_diagram(diagram,5);self.assertNotIn('check',result)
  with self.assertRaises(ValueError):validate_structured_diagram(diagram,6)
  diagram['edges'][0]['to']='missing'
  with self.assertRaises(ValueError):validate_structured_diagram(diagram,None)
 def circuit(self):
  return {'kind':'circuit','nodes':[{'id':'p','x':0,'y':0},{'id':'a','x':3,'y':0},{'id':'b','x':3,'y':2},{'id':'n','x':0,'y':2}], 'wires':[{'from':'a','to':'b'}],'components':[{'id':'V','type':'battery','from':'p','to':'n','value':12},{'id':'R','type':'resistor','from':'p','to':'a','value':6},{'id':'S','type':'switch','from':'b','to':'n','closed':True}],'check':{'operation':'total_current'}}
 def test_graph_circuit_uses_connections_not_fixed_picture(self):
  diagram=self.circuit();result=validate_structured_diagram(diagram,2);self.assertEqual(len(result['components']),3);self.assertNotIn('check',result)
  with self.assertRaises(ValueError):validate_structured_diagram(diagram,3)
  diagram['components'][2]['closed']=False;self.assertTrue(validate_structured_diagram(diagram,0))
 def test_fraction_and_root_options_are_numerically_checked(self):
  from practice_diagrams import numeric_option
  self.assertAlmostEqual(numeric_option(r'\(\frac{1}{2}\)'),.5)
  self.assertAlmostEqual(numeric_option(r'\(\frac{1}{\sqrt{2}}\)'),1/math.sqrt(2))
  self.assertAlmostEqual(numeric_option(r'\(\sqrt{4}\,\mathrm{A}\)'),2)
  self.assertAlmostEqual(numeric_option(r'\(2\times10^{3}\)'),2000)
  with self.assertRaises(ValueError):numeric_option(r'\(\href{bad}{2}\)')
 def test_parallel_network_and_voltage_targets(self):
  graph={'kind':'circuit','nodes':[{'id':'p','x':0,'y':0},{'id':'a','x':3,'y':0},{'id':'n','x':0,'y':3},{'id':'b','x':3,'y':3},{'id':'c','x':5,'y':0},{'id':'d','x':5,'y':3}], 'components':[{'id':'V','type':'battery','from':'p','to':'n','value':12},{'id':'R1','type':'resistor','from':'a','to':'b','value':6},{'id':'R2','type':'resistor','from':'c','to':'d','value':3}], 'wires':[{'from':'p','to':'a'},{'from':'a','to':'c'},{'from':'n','to':'b'},{'from':'b','to':'d'}],'check':{'operation':'total_current'}}
  self.assertTrue(validate_structured_diagram(graph,6));graph['check']={'operation':'resistor_voltage','componentId':'R2'};self.assertTrue(validate_structured_diagram(graph,12))
 def test_evaluator_rejects_bools_huge_powers_and_attribute_access(self):
  from practice_diagrams import expression_function
  for expression in ['True','2**100000','x.__class__','[x][0]','sin(x,2)']:
   with self.assertRaises(ValueError):expression_function(expression)(1)
 def test_chart_pie_requires_positive_total(self):
  with self.assertRaises(ValueError):validate_structured_diagram({'kind':'pie','values':[{'label':'a','value':0},{'label':'b','value':0}]},None)
if __name__=='__main__':unittest.main()
