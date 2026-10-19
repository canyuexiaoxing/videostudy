import tempfile,unittest,os,json
from pathlib import Path
from unittest.mock import patch
from overview_chat import save_overview_conversation,reply_to_overview
class OverviewChatTest(unittest.TestCase):
 def test_same_initial_messages_are_replayed_and_only_followups_returned(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'KEYFRAME_DIR':folder}):
   course='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';initial=[{'role':'system','content':'original system'},{'role':'user','content':'hidden original course input'}]
   result={'status':'completed','conversationId':'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'}
   save_overview_conversation(course,result,initial,{'headline':'original response'},'test-model')
   captured=[]
   answer=reply_to_overview(course,result,{},[{'role':'user','content':'earlier question'},{'role':'assistant','content':'earlier answer'}],'explain more',lambda messages,model:(captured.append((messages,model)) or {'reply':'follow-up reply','sourceIds':[]}))
   self.assertEqual(captured[0][0][:2],initial);self.assertEqual(captured[0][0][2]['role'],'assistant');self.assertIn('original response',captured[0][0][2]['content']);self.assertEqual(captured[0][1],'test-model');self.assertEqual(captured[0][0][-1]['content'],'explain more');self.assertEqual(answer,{'reply':'follow-up reply','citations':[],'contextMode':'original'})
 def test_missing_original_context_recovers_saved_overview_without_model_regeneration(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'KEYFRAME_DIR':folder}):
   source={'segments':[{'id':'s1','startMs':0,'endMs':1000,'text':'teacher method'}],'pageGroups':[]}
   captured=[]
   answer=reply_to_overview('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',{'status':'completed','headline':'saved overview'},source,[],'why',lambda messages,model:(captured.append(messages) or {'reply':'answer','sourceIds':['s1']}))
   self.assertEqual(answer['contextMode'],'restored');self.assertEqual(answer['citations'][0]['sourceId'],'s1');self.assertIn('teacher method',captured[0][1]['content']);self.assertIn('saved overview',captured[0][2]['content'])
 def test_new_overview_saves_real_conversation_and_chat_uses_provider_messages(self):
  from overview import build_overview
  from test_overview_required_notes import response,SPEECH
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'KEYFRAME_DIR':folder,'DEEPSEEK_API_KEY':'TEST_ONLY'}):
   course='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
   overview=build_overview(SPEECH,[],lambda _:response(),course_id=course)
   self.assertIn('conversationId',overview)
   with patch('overview_chat.request_model_json',return_value={'reply':'next answer','sourceIds':['s1']}) as provider:
    result=reply_to_overview(course,overview,{'segments':SPEECH},[],'why')
   body=json.loads(provider.call_args.args[0].data)
   self.assertEqual(result['contextMode'],'original');self.assertEqual([m['role'] for m in body['messages']],['system','user','assistant','system','user']);self.assertEqual(body['messages'][-1]['content'],'why');self.assertIn('speech',body['messages'][1]['content'])
 def test_invented_citation_is_not_saved_as_course_evidence(self):
  with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'KEYFRAME_DIR':folder}):
   with self.assertRaisesRegex(ValueError,'invalid_chat_citation'):
    reply_to_overview('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',{'status':'completed'},{},[],'why',lambda *_:{'reply':'made up','sourceIds':['unknown']})
 def test_invalid_citations_and_invalid_course_are_rejected(self):
  with self.assertRaises(ValueError):reply_to_overview('../other',{}, {},[],'x',lambda *_:{})
if __name__=='__main__':unittest.main()
