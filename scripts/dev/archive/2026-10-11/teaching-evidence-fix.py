from pathlib import Path
root=Path(r'E:\workp\videostudy')
p=root/'agent-python/mind_map.py';s=p.read_text(encoding='utf-8').replace('grounded-mind-map-v4-teaching-roles','grounded-mind-map-v5-teaching-evidence')
s=s.replace('"and examples (an array with title and sourceIds, separate from children). "','''"and examples (an array with title and sourceIds, separate from children). "
        "Also return teachingSourceIds and exampleSourceIds: arrays classifying the supplied speech IDs by the "
        "PURPOSE OF THE PASSAGE before building nodes. teachingSourceIds are independent concept lessons; "
        "exampleSourceIds include reading a question, explaining its conditions, choosing formulas, calculating, "
        "checking answers and the subsequent discussion of THIS question. Omit unrelated chatter from both lists. "
        "Question review remains example speech even when phrased like a general rule or method. Do not classify "
        "a formula reminder or generalization tied to the current question as independent teaching. "
        "Independent teaching needs a distinct transition into a concept lesson beyond the current problem. "
        "Only teachingSourceIds may support core leaves; a node-level new_knowledge label is not proof. "
        "Example opening and closing citations must span the complete question discussion, including review after "
        "the numerical answer. Do not fragment one problem into many calculation-step examples. "
        "previousSpeech and followingSpeech give boundary context only; cite IDs from segments, never context IDs. "''')
s=s.replace('''            "contentPolicy": PROMPT_VERSION,''','''            "contentPolicy": PROMPT_VERSION,
            "previousSpeech": [{"text": item["text"]} for item in valid[max(0, offset - 12):offset]],
            "followingSpeech": [{"text": item["text"]} for item in valid[offset + CHUNK_SEGMENTS:offset + CHUNK_SEGMENTS + 8]],''')
s=s.replace('''            visited = 0
            candidates''','''            classified = isinstance(answer.get('teachingSourceIds'), list)
            teaching_ids = {sid for sid in answer.get('teachingSourceIds', []) if isinstance(sid, str) and sid in sources} if classified else set()
            example_ids = {sid for sid in answer.get('exampleSourceIds', []) if isinstance(sid, str) and sid in sources} if isinstance(answer.get('exampleSourceIds'), list) else set()
            teaching_ids -= example_ids
            visited = 0
            candidates''')
s=s.replace("node['_ownEvidence'] = has_own_evidence","node['_ownEvidence'] = has_own_evidence\n                node['_dedicatedSourceIds'] = sorted(teaching_ids) if classified else None")
anchor='''            if concepts:
                chapter_title'''
replace='''            # Extend truncated example endings to include classified follow-up discussion.
            examples.sort(key=lambda item: item['startMs'])
            for sid in example_ids:
                source = sources[sid]
                preceding = [example for example in examples if example['startMs'] <= source['startMs']]
                if not preceding:
                    continue
                target = preceding[-1]
                if any(ref['sourceId'] == sid for ref in target['evidenceRefs']):
                    continue
                target['evidenceRefs'].append(dict(sourceType='transcript', sourceId=sid,
                    startMs=source['startMs'], endMs=source['endMs'], quote=source['text']))
                target['evidenceRefs'].sort(key=lambda ref: ref['startMs'])
                target['endMs'] = max(ref['endMs'] for ref in target['evidenceRefs'])
            if concepts:
                chapter_title'''
assert anchor in s;s=s.replace(anchor,replace)
s=s.replace("has_own_evidence = node.pop('_ownEvidence', False)","has_own_evidence = node.pop('_ownEvidence', False)\n        dedicated_ids = node.pop('_dedicatedSourceIds', None)")
s=s.replace("refs = [ref for ref in node['evidenceRefs'] if role == 'new_knowledge' or not any(\n            start <= ref['startMs'] and ref['endMs'] <= end for start, end in ranges)] if has_own_evidence else []", "refs = [ref for ref in node['evidenceRefs'] if (ref['sourceId'] in dedicated_ids if dedicated_ids is not None else not any(\n            start <= ref['startMs'] and ref['endMs'] <= end for start, end in ranges))] if has_own_evidence else []")
p.write_text(s,encoding='utf-8')
