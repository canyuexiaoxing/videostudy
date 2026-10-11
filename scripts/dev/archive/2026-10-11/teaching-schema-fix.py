from pathlib import Path
root=Path(r'E:\workp\videostudy')
p=root/'agent-python/mind_map.py';s=p.read_text(encoding='utf-8')
s=s.replace('''            return answer
        except (HTTPError''','''            if payload.get('segments') and (not isinstance(answer.get('teachingSourceIds'), list) or
                    not isinstance(answer.get('exampleSourceIds'), list)):
                raise MindMapResponseError("Required teachingSourceIds and exampleSourceIds arrays are missing")
            return answer
        except (HTTPError''')
s=s.replace('"Fix syntax and required fields using the original evidence. Preserve sourceIds; "','"Fix syntax and required fields, including teachingSourceIds and exampleSourceIds arrays, using the original evidence. Preserve sourceIds; "')
p.write_text(s,encoding='utf-8')
p=root/'agent-python/test_mind_map.py';s=p.read_text(encoding='utf-8').replace("return provider_response(json.dumps({'topic': '章节', 'children': [", "return provider_response(json.dumps({'topic': '章节', 'teachingSourceIds': [item['id'] for item in payload['segments']], 'exampleSourceIds': [], 'children': [")
p.write_text(s,encoding='utf-8')
