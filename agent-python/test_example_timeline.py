import unittest
from example_timeline import group_examples, question_opening

def segment(i,t,text):return dict(id=str(i),startMs=t,endMs=t+900,text=text)
def node(i,ss):return dict(id=str(i),title='计算步骤'+str(i),startMs=ss[0]['startMs'],endMs=ss[-1]['endMs'],children=[],evidenceRefs=[dict(sourceType='transcript',sourceId=s['id'],startMs=s['startMs'],endMs=s['endMs'],quote=s['text']) for s in ss])
class ExampleTimelineTest(unittest.TestCase):
 def test_chunks_merge_at_question_openings_and_references_do_not_open_questions(self):
  ss=[segment(1,0,'第一题开始'),segment(2,1000,'算出结果'),segment(3,2000,'再来第二题'),segment(4,3000,'所以这个题用洛必达'),segment(5,4000,'不是第一题，也不是第二题那样'),segment(6,5000,'再往下看第三题'),segment(7,6000,'代入计算')]
  raw=[node(1,ss[:2]),node(2,ss[2:3]),node(3,ss[3:5]),node(4,ss[5:]),node(5,ss[6:])]
  grouped=group_examples(raw,ss)
  self.assertEqual(len(grouped),3);self.assertEqual([n['startMs'] for n in grouped],[0,2000,5000]);self.assertEqual(grouped[1]['endMs'],4900)
  self.assertEqual(len(grouped[2]['evidenceRefs']),2);self.assertEqual(len(raw),5)
 def test_no_opening_evidence_does_not_guess_merge_by_close_times_or_similar_titles(self):
  ss=[segment(1,0,'计算'),segment(2,1000,'计算')];raw=[node(1,ss[:1]),node(2,ss[1:])]
  self.assertEqual(group_examples(raw,ss),raw)
 def test_board_lecture_transitions_accept_numbered_asr_variants_but_ignore_comparisons(self):
  ss=[segment(1,0,'开始讲题'),segment(2,1000,'再往下看第七体'),segment(3,2000,'第七题和第八题很像'),segment(4,3000,'同样再看第八个'),segment(5,4000,'再往下再看一个大题题九题')]
  grouped=group_examples([node(i,[s]) for i,s in enumerate(ss)],ss)
  self.assertEqual([n['startMs'] for n in grouped],[0,1000,3000,4000])
 def test_merged_results_are_idempotent_and_keep_grounded_times(self):
  ss=[segment(1,0,'第一题'),segment(2,2000,'再来第二题'),segment(3,3000,'继续计算')]
  grouped=group_examples([node(1,ss[:1]),node(2,ss[1:2]),node(3,ss[2:])],ss)
  self.assertEqual(group_examples(grouped,ss),grouped)

 def test_bare_reference_to_previous_question_is_not_an_opening(self):
  ss=[segment(1,0,'再来看第十一题'),segment(2,1000,'第五题'),segment(3,2000,'继续讲第十一题')]
  self.assertEqual(len(group_examples([node(i,[s]) for i,s in enumerate(ss)],ss)),1)
 def test_question_opening_inside_sparse_example_range_is_not_lost(self):
  ss=[segment(1,0,'第一题开始'),segment(2,1000,'再来第二题'),segment(3,2000,'再来第三题'),segment(4,3000,'计算结果')]
  grouped=group_examples([node(1,[ss[0],ss[-1]])],ss)
  self.assertEqual([n['startMs'] for n in grouped],[0,1000,2000]);self.assertEqual(grouped[1]['title'],'例题 2')

 def test_reference_guard_is_scoped_to_opening_not_later_comparison(self):
  self.assertIsNone(question_opening('再看第一题的方法，这个题也可以用洛必达'))
  self.assertIsNone(question_opening('我们再来看第二题的结论'))
  self.assertEqual(question_opening('再看第九题，但不是前面第一题那种做法'),9)
 def test_mixed_numbered_and_unnumbered_questions_remain_separate(self):
  ss=[segment(1,0,'第一题开始'),segment(2,1000,'第一题答案'),segment(3,2000,'来看这道例题'),segment(4,3000,'第二道题答案'),segment(5,4000,'下面看另一个例子')]
  self.assertEqual([n['startMs'] for n in group_examples([node(1,ss[:2]),node(2,ss[2:4]),node(3,ss[4:])],ss)],[0,2000,4000])

 def test_rechecking_current_question_does_not_start_another_question(self):
  ss=[segment(1,0,'第一题开始'),segment(2,1000,'计算分子的极限'),segment(3,2000,'再看这道题，分母趋于零，所以用洛必达'),segment(4,3000,'代入算出第一题答案')]
  self.assertEqual(len(group_examples([node(1,ss)],ss)),1)
