"""Offline final-course grounding, citation, identity and cache regressions."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from checkpoints import Checkpoints
try:
    from course_mind_map import build_course_mind_map
except ImportError:
    build_course_mind_map = None


def knowledge(page, ms):
    return {'id':f'page_{page}_knowledge_1','title':'a²+b²=c²','kind':'formula',
            'sourceIds':[], 'imageIds':[f'frame_{ms}'],
            'details':[{'title':'Only for right triangles','sourceIds':[], 'imageIds':[f'frame_{ms}']}]}


def example(page, ms, sid):
    return {'id':f'page_{page}_example_1','title':f'Question {page}', 'sourceIds':[sid], 'imageIds':[f'frame_{ms}']}


def answer(**changes):
    return dict({'topic':'Triangles','children':[],'examples':[],'uncertainties':[]},**changes)


class CourseMindMapTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(build_course_mind_map,'Final whole-course module is required')
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.pages=[];self.visuals=[];self.segments=[]
        for page,ms in [(1,1000),(2,3000),(3,5000)]:
            cv2.imwrite(str(self.root/f'{ms}.jpg'),np.full((30,40,3),100+page,np.uint8))
            self.pages.append({'pageIndex':page,'firstFrameTimeMs':ms,'lastFrameTimeMs':ms,
                'memberFrameTimesMs':[ms],'representativeFrameTimesMs':[ms],
                'groupUnderstanding':{'status':'completed','knowledgeCandidates':[],
                    'exampleCandidates':[],'connections':{},'uncertainties':[], 'forwardImageTimesMs':[]}})
            self.visuals.append({'frameTimeMs':ms,'ocrBlocks':[]})
            self.segments.append({'id':f's{page}','startMs':ms-100,'endMs':ms+100,'text':f'Original question {page}'})
        self.pages[0]['groupUnderstanding']['knowledgeCandidates']=[knowledge(1,1000)]

    def build(self,provider,**kwargs):
        return build_course_mind_map(self.segments,self.pages,self.visuals,self.root,ask_json=provider,**kwargs)

    def core_answer(self):
        return answer(children=[{'title':'a²+b²=c²','candidateIds':['page_1_knowledge_1'],
            'sourceIds':[], 'imageIds':['frame_1000'], 'details':[{'title':'Only for right triangles',
            'sourceIds':[], 'imageIds':['frame_1000']}], 'children':[]}])

    def add_examples(self):
        for n,ms in [(2,3000),(3,5000)]:
            self.pages[n-1]['groupUnderstanding']['exampleCandidates']=[example(n,ms,f's{n}')]

    def merged_answer(self,**extra):
        return self.core_answer() | {'examples':[{'title':'One complete question',
            'candidateIds':['page_2_example_1','page_3_example_1'],
            'sourceIds':['s2','s3'],'imageIds':['frame_3000','frame_5000'],**extra}]}

    def test_duplicate_concept_candidate_cannot_create_two_entries(self):
        raw=self.core_answer();raw['children']*=2
        result=self.build(lambda p,imgs:raw)
        self.assertEqual(len(result['root']['children']),1)
        self.assertEqual(result['status'],'failed')

    def test_failed_group_forwards_corresponding_speech_with_original_image(self):
        self.pages[1]['groupUnderstanding'].update(status='failed',forwardImageTimesMs=[3000])
        calls=[]
        self.build(lambda p,imgs:calls.append(p) or self.core_answer())
        self.assertIn('s2',calls[0]['firstHandSourceIds'])
        self.assertIn('s2',[r['sourceId'] for r in calls[0]['sourceEvidence']])
        self.assertNotIn('s3',calls[0]['firstHandSourceIds'])

    def test_final_can_move_misclassified_question_out_of_knowledge(self):
        cid='page_1_knowledge_1'
        raw=answer(candidateDecisions=[{'candidateIds':[cid],'target':'example',
            'reason':'原图题干和给定数值表明这里是具体例题代入过程', 'sourceIds':[], 'imageIds':['frame_1000']}],
            examples=[{'title':'模拟完整例题','candidateIds':[cid],'sourceIds':[], 'imageIds':['frame_1000']}])
        result=self.build(lambda p,imgs:raw)
        self.assertEqual(result['root']['children'],[])
        self.assertEqual(len(result['examples']),1)
        self.assertEqual(result['status'],'empty')
        raw['candidateDecisions'][0]['imageIds']=['frame_9999']
        rejected=self.build(lambda p,imgs:raw)
        self.assertEqual(len(rejected['root']['children']),1)
        self.assertEqual(rejected['status'],'failed')

    def test_reclassified_example_retains_solution_detail_evidence_and_decision_rationale(self):
        self.segments.append({'id':'solution','startMs':1200,'endMs':1300,'text':'具体解题条件'})
        candidate=self.pages[0]['groupUnderstanding']['knowledgeCandidates'][0]
        candidate['details']=[{'title':'题目解答条件','sourceIds':['solution'],'imageIds':[]}]
        raw=answer(candidateDecisions=[{'candidateIds':[candidate['id']],'target':'example',
            'reason':'原图给定数值说明这是具体例题而非独立知识', 'sourceIds':[], 'imageIds':['frame_1000']}],
            examples=[{'title':'完整题目','candidateIds':[candidate['id']],'sourceIds':[], 'imageIds':['frame_1000']}])
        result=self.build(lambda p,imgs:raw)
        self.assertIn('solution',[r['sourceId'] for r in result['examples'][0]['evidenceRefs']])
        self.assertTrue(any('具体例题而非独立知识' in note and 'frame_1000' in note for note in result['uncertainties']))

    def test_unspoken_formula_and_details_use_real_image_evidence_and_program_ids(self):
        result=self.build(lambda p,imgs:self.core_answer())
        self.assertEqual(result['status'],'completed')
        node=result['root']['children'][0]
        self.assertEqual(node['title'],'a²+b²=c²')
        self.assertEqual((node['startMs'],node['endMs']),(1000,1000))
        self.assertEqual(node['evidenceRefs'],[{'sourceType':'image','sourceId':'frame_1000','startMs':1000,'endMs':1000,'quote':'课件截图'}])
        self.assertEqual(node['details'][0]['evidenceRefs'],node['evidenceRefs'])
        self.assertNotEqual(node['id'],'page_1_knowledge_1')

    def test_final_payload_only_sends_actual_group_references_not_all_course_speech(self):
        calls=[]
        self.build(lambda p,imgs:calls.append((p,imgs)) or self.core_answer())
        payload,images=calls[0]
        self.assertEqual(payload['sourceEvidence'],[])
        self.assertEqual([i['sourceId'] for i in payload['imageEvidence']],['frame_1000'])
        self.assertEqual(images,[])
        self.assertEqual([c['id'] for c in payload['concepts']],['page_1_knowledge_1'])

    def test_failed_or_partial_group_original_images_go_directly_to_final(self):
        self.pages[1]['groupUnderstanding'].update(status='partial',uncertainties=['Formula blurry'],forwardImageTimesMs=[3000])
        calls=[]
        result=self.build(lambda p,imgs:calls.append((p,imgs)) or (self.core_answer() | {'children':self.core_answer()['children']+[
            {'title':'Visible second formula','sourceIds':[],'imageIds':['frame_3000'],'children':[]}], 'uncertainties':['Part of diagram remains unreadable']}))
        self.assertEqual([(ms,detail) for ms,_,detail in calls[0][1]],[(3000,'original')])
        self.assertIn('Visible second formula',[n['title'] for n in result['root']['children']])
        self.assertIn('Part of diagram remains unreadable',result['uncertainties'])
        self.assertEqual(result['status'],'completed')

    def test_unknown_image_speech_and_unrelated_course_speech_are_dropped(self):
        for reference in ({'imageIds':['frame_9999']},{'sourceIds':['invented']},{'sourceIds':['s3']}):
            with self.subTest(reference=reference):
                result=self.build(lambda p,imgs:answer(children=[{'title':'Forged claim','children':[],**reference}]))
                self.assertEqual(result['status'],'failed')
                self.assertNotIn('Forged claim',[n['title'] for n in result['root']['children']])
                self.assertTrue(result['uncertainties'])

    def test_source_free_detail_is_discarded_and_marks_partial_map_failed(self):
        reply=self.core_answer()
        reply['children'][0]['details'].append({'title':'Unsupported extra condition','sourceIds':[],'imageIds':[]})
        result=self.build(lambda *_:reply)
        self.assertEqual(result['status'],'failed')
        self.assertNotIn('Unsupported extra condition',[detail['title'] for detail in result['root']['children'][0]['details']])

    def test_example_citations_cannot_be_promoted_into_core_knowledge(self):
        self.add_examples()
        result=self.build(lambda p,imgs:answer(children=[{'title':'General looking claim','candidateIds':['page_2_example_1'], 'sourceIds':['s2'], 'children':[]}]))
        self.assertNotIn('General looking claim',[n['title'] for n in result['root']['children']])
        self.assertEqual(len(result['examples']),2)
        self.assertEqual(result['status'],'failed')

    def test_same_subject_and_key_do_not_merge_different_questions(self):
        self.add_examples()
        result=self.build(lambda p,imgs:self.merged_answer(subject='Triangles',key='triangle'))
        self.assertEqual(len(result['examples']),2)
        self.assertEqual([e['title'] for e in result['examples']],['Question 2','Question 3'])
        self.assertEqual(result['status'],'failed')

    def test_cross_page_question_merges_only_with_grounded_continuation(self):
        self.add_examples()
        self.pages[1]['groupUnderstanding']['connections']={'next':{'relation':'example_continuation',
            'sourceIds':['s2','s3'],'imageIds':['frame_3000','frame_5000'],'reason':'Same numbered question continues its derivation'}}
        result=self.build(lambda p,imgs:self.merged_answer())
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len(result['examples']),1)
        self.assertEqual((result['examples'][0]['startMs'],result['examples'][0]['endMs']),(2900,5100))
        self.assertEqual([r['quote'] for r in result['examples'][0]['evidenceRefs'] if r['sourceType']=='transcript'],['Original question 2','Original question 3'])

    def test_final_merge_evidence_must_cover_both_actual_pages(self):
        self.add_examples()
        valid={'reason':'Question 2 stem and given values match; later slide completes its calculation',
               'sourceIds':[], 'imageIds':['frame_3000','frame_5000']}
        result=self.build(lambda p,imgs:self.merged_answer(mergeEvidence=valid))
        self.assertEqual(len(result['examples']),1)
        invalid=dict(valid,imageIds=['frame_3000'])
        result=self.build(lambda p,imgs:self.merged_answer(mergeEvidence=invalid))
        self.assertEqual(len(result['examples']),2)
        self.assertEqual(result['status'],'failed')

    def test_different_questions_on_same_page_cannot_merge_by_shared_image(self):
        self.add_examples()
        group=self.pages[1]['groupUnderstanding']
        second=dict(example(2,3000,'s2'),id='page_2_example_2',title='Distinct question on same slide')
        group['exampleCandidates'].append(second)
        merged={'title':'Bad merged question','candidateIds':['page_2_example_1','page_2_example_2'],
                'sourceIds':['s2'],'imageIds':['frame_3000'],
                'mergeEvidence':{'reason':'Question stem looks similar on the same slide', 'sourceIds':['s2'],'imageIds':['frame_3000']}}
        result=self.build(lambda p,imgs:self.core_answer() | {'examples':[merged]})
        self.assertEqual(len(result['examples']),3)
        self.assertNotIn('Bad merged question',[n['title'] for n in result['examples']])
        self.assertEqual(result['status'],'failed')

    def test_unreadable_original_jpg_is_not_used_as_visual_evidence(self):
        (self.root/'1000.jpg').write_bytes(b'not a jpeg')
        result=self.build(lambda p,imgs:self.core_answer())
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['root']['children'],[])
        self.assertTrue(result['uncertainties'])

    def test_duplicate_example_candidate_has_one_entry_even_with_multiple_provider_nodes(self):
        self.add_examples()
        first={'title':'Question 2','candidateIds':['page_2_example_1'],'sourceIds':['s2'],'imageIds':[]}
        result=self.build(lambda p,imgs:self.core_answer() | {'examples':[first,dict(first,title='Question 2 answer')]})
        self.assertEqual(len(result['examples']),2)
        self.assertEqual(sum(any(r['sourceId']=='s2' for r in node['evidenceRefs']) for node in result['examples']),1)

    def test_provider_failure_and_malformed_reply_keep_grounded_partial_structure(self):
        self.add_examples()
        for provider in (lambda *_: (_ for _ in ()).throw(OSError('offline')), lambda *_:'not JSON', lambda *_:{'topic':'bad','children':'bad'}):
            with self.subTest(provider=provider):
                result=self.build(provider)
                self.assertEqual(result['status'],'failed')
                self.assertEqual(result['root']['children'][0]['title'],'a²+b²=c²')
                self.assertEqual(len(result['examples']),2)
                self.assertTrue(result['uncertainties'])

    def test_cancelled_before_and_after_reply_never_publishes_late_provider_nodes(self):
        signal=threading.Event();signal.set()
        calls=[]
        result=self.build(lambda p,imgs:calls.append(True) or self.core_answer(),signal=signal)
        self.assertEqual(calls,[]);self.assertEqual(result['status'],'failed')
        signal.clear()
        def late(p,imgs):
            signal.set()
            return self.core_answer() | {'topic':'Late provider title'}
        result=self.build(late,signal=signal)
        self.assertNotEqual(result['root']['title'],'Late provider title')
        self.assertEqual(result['status'],'failed')

    def test_checkpoint_changes_for_group_revisions_speech_and_image_bytes_and_never_saves_failed(self):
        cp=Checkpoints(self.root/'.cache',{})
        calls=[]
        provider=lambda p,imgs:calls.append(True) or self.core_answer()
        self.build(provider,checkpoint=cp);self.build(provider,checkpoint=cp)
        self.assertEqual(len(calls),1)
        self.pages[0]['_revision']=2
        self.build(provider,checkpoint=cp);self.assertEqual(len(calls),2)
        cv2.imwrite(str(self.root/'1000.jpg'),np.full((30,40,3),22,np.uint8))
        self.build(provider,checkpoint=cp);self.assertEqual(len(calls),3)
        self.segments[0]['text']='Revised actual speech'
        self.build(provider,checkpoint=cp);self.assertEqual(len(calls),4)
        cp2=Checkpoints(self.root/'.failed-cache',{})
        bad=[]
        broken=lambda *_:bad.append(True) or {'children':'malformed'}
        self.build(broken,checkpoint=cp2);self.build(broken,checkpoint=cp2)
        self.assertEqual(len(bad),2)

    def test_default_provider_masks_ignored_pixels_before_encoding_image(self):
        import base64
        import course_mind_map as module
        self.pages[1]['_visualRegions']={'x':.5,'y':0,'width':.5,'height':1}
        self.pages[1]['groupUnderstanding'].update(status='failed',forwardImageTimesMs=[3000])
        seen=[]
        class Response:
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer())}}]}).encode()
        def transport(request,timeout):
            body=json.loads(request.data)
            self.assertEqual(body['max_tokens'],393216)
            self.assertEqual(timeout,300)
            for item in body['messages'][1]['content']:
                if item.get('type')=='image_url':
                    data=base64.b64decode(item['image_url']['url'].split(',')[1])
                    image=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
                    seen.append(image)
            return Response()
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'offline-fixture'}),patch.object(module,'urlopen',side_effect=transport):
            build_course_mind_map(self.segments,self.pages,self.visuals,self.root)
        self.assertEqual(len(seen),1)
        self.assertGreater(int(seen[0][:,22:].min()),245)
        self.assertLess(int(seen[0][:,:18].max()),120)

    def test_recursion_and_count_are_bounded_and_node_ids_unique(self):
        leaf={'title':'Formula','imageIds':['frame_1000'],'sourceIds':[],'children':[]}
        deep=copy.deepcopy(leaf)
        for _ in range(30):deep={'title':'Section','children':[deep]}
        result=self.build(lambda *_:answer(children=[deep]+[copy.deepcopy(leaf) for _ in range(4200)]))
        nodes=[];pending=[result['root']]+result['examples']
        while pending:
            node=pending.pop();nodes.append(node);pending.extend(node.get('children',[]))
        self.assertLessEqual(len(nodes),4096)
        self.assertEqual(len({node['id'] for node in nodes}),len(nodes))
        self.assertEqual(result['status'],'failed')


if __name__=='__main__':unittest.main()
