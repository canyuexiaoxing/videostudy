from pathlib import Path
root=Path(r'E:\workp\videostudy')
p=root/'agent-python/mind_map.py';s=p.read_text(encoding='utf-8')
s=s.replace('grounded-mind-map-v3-core-examples','grounded-mind-map-v4-teaching-roles')
s=s.replace('"Extract general formulas/methods taught during an example as core knowledge, with their speech citations. "', '''"Classify each knowledge node with teachingRole: explanation (dedicated concept teaching), application "
        "(using an existing concept to solve a problem), or new_knowledge (a genuinely new independent explanation "
        "introduced during a worked example). Classify by the purpose of the speech passage, not whether it mentions a formula. "
        "Do not output application nodes in children: formula reminders, substitutions and uses belong to examples. "
        "When an earlier passage teaches a formula and later examples use it, cite only the dedicated teaching passage "
        "for the core knowledge node; keep all later uses in examples, even when the wording sounds general. "
        "Use new_knowledge only for a distinct definition, derivation or applicability condition being taught for the first "
        "time, never for recalling an already taught formula. Keep new knowledge separate from calculation steps. "''')
old='return _node(f"node_{offset}_{index}", title.strip()[:80], refs, children)'
new='''node = _node(f"node_{offset}_{index}", title.strip()[:80], refs, children)
                node['_teachingRole'] = raw.get('teachingRole', 'explanation')
                return node'''
assert old in s;s=s.replace(old,new)
old='''    root_refs = chapters[0]["evidenceRefs"] if chapters else []'''
new='''    # Verified example intervals are applications unless an independent new explanation is explicit.
    # Prune after all chunks finish so ancestors can be rebuilt from retained evidence.
    ranges = [(example['startMs'], example['endMs']) for example in examples]
    def dedicated_teaching(node):
        role = node.pop('_teachingRole', 'explanation')
        if role == 'application':
            return None
        original_children = node['children']
        children = [retained for child in original_children
                    if (retained := dedicated_teaching(child)) is not None]
        if original_children and not children:
            return None
        refs = [ref for ref in node['evidenceRefs'] if role == 'new_knowledge' or not any(
            start <= ref['startMs'] and ref['endMs'] <= end for start, end in ranges)]
        if not refs and children:
            refs = children[0]['evidenceRefs']
        if not refs:
            return None
        return _node(node['id'], node['title'], refs, children)
    chapters = [retained for node in chapters if (retained := dedicated_teaching(node)) is not None]
    root_refs = chapters[0]["evidenceRefs"] if chapters else []'''
assert old in s;s=s.replace(old,new);p.write_text(s,encoding='utf-8')
p=root/'agent-python/test_core_mind_map.py';s=p.read_text(encoding='utf-8').replace('test_example_range_filters_other_chunks_and_empty_groups','test_example_range_prunes_empty_groups_without_losing_other_chunks');p.write_text(s,encoding='utf-8')
