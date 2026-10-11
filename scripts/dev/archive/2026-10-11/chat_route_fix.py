from pathlib import Path
p=Path('E:/workp/videostudy/agent-python/test_question_chat.py')
s=p.read_text(encoding='utf-8')
s=s.replace('        from fastapi.testclient import TestClient\n', '        import asyncio, json\n')
s=s.replace("            response=TestClient(app).post('/question-chat',json={'context':self.context(),'history':[],'message':'为什么'})\n        self.assertEqual(response.status_code,200)\n        self.assertEqual(response.json()['citations'],self.context()['evidence'])", '''            events=[]
            async def receive():
                return {'type':'http.request','body':json.dumps({'context':self.context(),'history':[],'message':'为什么'}).encode(),'more_body':False}
            async def send(event): events.append(event)
            scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST','scheme':'http','path':'/question-chat','raw_path':b'/question-chat','query_string':b'','root_path':'','headers':[(b'content-type',b'application/json')],'server':('test',80),'client':('test',123)}
            asyncio.run(app(scope,receive,send))
        self.assertEqual(events[0]['status'],200)
        self.assertEqual(json.loads(events[1]['body'])['citations'],self.context()['evidence'])''')
p.write_text(s,encoding='utf-8')
