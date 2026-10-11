from pathlib import Path
p=Path(r'E:\workp\videostudy\agent-python\mind_map.py');s=p.read_text(encoding='utf-8')
s=s.replace('''                refs.sort(key=lambda ref: ref["startMs"])
                if not refs and children:''','''                refs.sort(key=lambda ref: ref["startMs"])
                has_own_evidence = bool(refs)
                if not refs and children:''')
s=s.replace("node['_teachingRole'] = raw.get('teachingRole', 'explanation')","node['_teachingRole'] = raw.get('teachingRole', 'explanation')\n                node['_ownEvidence'] = has_own_evidence")
s=s.replace("role = node.pop('_teachingRole', 'explanation')","role = node.pop('_teachingRole', 'explanation')\n        has_own_evidence = node.pop('_ownEvidence', False)")
s=s.replace('''        if original_children and not children:
            return None
        refs = [ref for ref in node['evidenceRefs'] if role == 'new_knowledge' or not any(''','''        refs = [ref for ref in node['evidenceRefs'] if role == 'new_knowledge' or not any(''')
s=s.replace("start <= ref['startMs'] and ref['endMs'] <= end for start, end in ranges)]\n        if not refs and children:","start <= ref['startMs'] and ref['endMs'] <= end for start, end in ranges)] if has_own_evidence else []\n        if not refs and children:")
p.write_text(s,encoding='utf-8')
