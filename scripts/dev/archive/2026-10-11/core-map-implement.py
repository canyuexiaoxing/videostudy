from pathlib import Path
r=Path('E:/workp/videostudy')
def edit(name,changes):
 p=r/name;s=p.read_text(encoding='utf-8')
 for before,after in changes:
  assert before in s,(name,before)
  s=s.replace(before,after)
 p.write_text(s,encoding='utf-8')
edit('agent-python/mind_map.py',[
('import logging','import logging\nimport re'),
('PROMPT_VERSION = "grounded-mind-map-v2"','PROMPT_VERSION = "grounded-mind-map-v3-core-examples"\n# Preserve completed media/page checkpoints; map chunk inputs carry the new policy.\nCACHE_CONTEXT_PROMPT_VERSION = "grounded-mind-map-v2"'),
('"children (a recursive array of nodes with title, optional sourceIds, and optional children). "','''"children (a recursive array of CORE KNOWLEDGE nodes with title, kind=knowledge, optional sourceIds, and optional children), "
        "and examples (an array with title and sourceIds, separate from children). "
        "Core knowledge includes precise definitions, formulas with symbol meanings and applicability conditions, "
        "knowledge relationships, principles and general workflows, comparisons/distinctions, key points and common mistakes "
        "(核心概念、知识点关系、原理与流程、对比与区分、重点与易错点). Organize by the actual taught subject; do not force empty categories. "
        "Never put worked-example question statements, specific case numbers, substitutions, calculations or answers in children. "
        "Extract general formulas/methods taught during an example as core knowledge, with their speech citations. "
        "List actual worked examples separately in examples, citing their opening and final supporting speech segments "
        "so their video locations can be derived from real evidence. Return examples=[] if none. Never invent examples or times. "'''),
('            "pageHints": _page_hints', '            "contentPolicy": PROMPT_VERSION,\n            "pageHints": _page_hints'),
('            visited = 0\n\n            def convert', '''            visited = 0
            candidates = list(answer.get('examples', []))[:24] if isinstance(answer.get('examples'), list) else []
            def is_example(raw):
                return raw.get('kind') == 'example' or bool(re.match(
                    r'^(?:例题|例\\s*[0-9一二三四五六七八九十]|练习题|习题|worked example\\b|example\\b)',
                    str(raw.get('title', '')).strip(), re.IGNORECASE))

            def convert'''),
('                visited += 1\n                index = visited', '''                visited += 1
                if is_example(raw):
                    candidates.append(raw)
                    return None
                index = visited'''),
('            if concepts:\n                chapter_title', '''            examples = []
            seen_ranges = set()
            for raw in candidates[:48]:
                if not isinstance(raw, dict) or not isinstance(raw.get('title'), str) or not raw['title'].strip():
                    continue
                refs, pending, scanned = {}, [raw], 0
                while pending and scanned < MAX_NODES_PER_CHUNK:
                    item = pending.pop(); scanned += 1
                    if not isinstance(item, dict): continue
                    for source_id in item.get('sourceIds', [])[:CHUNK_SEGMENTS] if isinstance(item.get('sourceIds'), list) else []:
                        if isinstance(source_id, str) and source_id in sources:
                            source = sources[source_id]
                            refs[source_id] = dict(sourceType='transcript', sourceId=source_id,
                                startMs=source['startMs'], endMs=source['endMs'], quote=source['text'])
                    if isinstance(item.get('children'), list): pending.extend(item['children'][:MAX_NODES_PER_CHUNK])
                evidence = sorted(refs.values(), key=lambda ref: ref['startMs'])
                if not evidence: continue
                identity = (evidence[0]['startMs'], max(ref['endMs'] for ref in evidence))
                if identity in seen_ranges: continue
                seen_ranges.add(identity)
                examples.append(_node(f'example_{offset}_{len(examples)}', raw['title'].strip()[:80], evidence, []))
            if concepts:
                chapter_title'''),
('                return {"chapter": _node(f"chapter_{offset}", chapter_title,','                if is_example({"title": chapter_title}): chapter_title = "核心知识"\n                return {"examples": examples, "chapter": _node(f"chapter_{offset}", chapter_title,'),
('            elif raw_children:', '            elif raw_children and any(isinstance(item, dict) and not is_example(item) for item in raw_children):'),
('return {"chapter": None, "failed": True}', 'return {"chapter": None, "failed": True, "examples": []}'),
('return {"chapter": None, "failed": False}', 'return {"chapter": None, "failed": False, "examples": examples}'),
('    failed = any(result[\'failed\'] for result in results)', '    failed = any(result[\'failed\'] for result in results)\n    examples = sorted([example for result in results for example in result.get("examples", [])], key=lambda item: item["startMs"])'),
('"status": "empty" if not valid else "failed" if failed or not chapters else "completed"', '"status": "failed" if failed else "empty" if not chapters else "completed"'),
('            "root": _node("course", "课程知识导图", root_refs, chapters)}', '            "examples": examples,\n            "root": _node("course", "课程知识导图", root_refs, chapters)}'),
])
edit('agent-python/analysis.py',[('from mind_map import PROMPT_VERSION as MAP_VERSION','from mind_map import CACHE_CONTEXT_PROMPT_VERSION as MAP_VERSION')])
edit('backend-java/src/main/java/cn/videostudy/api/TranscriptionController.java',[
('String createdAt, MindMapNode root) {','''String createdAt, MindMapNode root, List<MindMapNode> examples) {
        public MindMapResult(String status, String provider, String modelId, String promptVersion, String createdAt, MindMapNode root) {
            this(status, provider, modelId, promptVersion, createdAt, root, null);
        }'''),
])
edit('backend-java/src/main/java/cn/videostudy/api/MindMapValidator.java',[
('        if (!validTree(map.root(), known)) return false;', '''        if (!validTree(map.root(), known)) return false;
        if (map.examples() != null) {
            if (map.examples().size() > 4096) return false;
            for (var example : map.examples()) {
                if (example == null || !validTree(example, known) || example.evidenceRefs().isEmpty() || !example.children().isEmpty()) return false;
                if (example.endMs() != example.evidenceRefs().stream().mapToLong(TranscriptionController.MindMapEvidence::endMs).max().orElse(0)) return false;
            }
        }'''),
])
edit('desktop/src/mindMap.ts',[('  root: MindMapNode\n}', '  root: MindMapNode\n  examples?: MindMapNode[] | null\n}')])
edit('desktop/src/App.vue',[
('没有可用的语音转写，暂时无法生成有出处的导图。', "{{ mindMap.examples?.length ? '本段课程未提取到核心知识，可通过下方例题节点回看。' : '没有可用的核心知识依据，暂时无法生成导图。' }}"),
('          <MindMapCanvas v-if="mindMap.root.children.length" :root="mindMap.root" @select="selectMindMapNode" />','''          <MindMapCanvas v-if="mindMap.root.children.length" :root="mindMap.root" @select="selectMindMapNode" />
          <section v-if="mindMap.examples?.length" class="example-timeline" aria-label="例题时间节点">
            <div class="example-timeline-heading"><h3>例题时间节点</h3><span>{{ mindMap.examples.length }} 个讲解片段</span></div>
            <p>例题独立列出，点击回看对应讲解。</p>
            <button v-for="example in mindMap.examples" :key="example.id" type="button" @click="selectMindMapNode(example)"><span class="time">{{ formatTime(example.startMs) }}</span><span>{{ example.title }}</span><StudyIcon name="play" /></button>
          </section>'''),
('点击节点，回看课程中的对应讲解','核心知识看导图，例题按时间回看'),
])
p=r/'desktop/src/study-design.css'
with p.open('a',encoding='utf-8') as f:f.write('''
.example-timeline{padding:16px 19px;border-top:1px solid #e7edf8;background:#fafcff}.example-timeline-heading{display:flex;align-items:center;justify-content:space-between;gap:10px}.example-timeline h3{margin:0;font-size:14px;color:#2e446f}.example-timeline-heading>span,.example-timeline>p{font-size:11px;color:#798baa}.example-timeline>p{margin:7px 0 10px}.example-timeline>button{display:flex;align-items:center;gap:12px;width:100%;padding:11px 4px;border:0;border-top:1px solid #e9eef7;background:transparent;color:#435a83;text-align:left;font-size:12px;cursor:pointer}.example-timeline>button:hover{color:#315dec;background:#f1f5ff}.example-timeline>button>.time{flex:none}.example-timeline>button>span:nth-child(2){flex:1;min-width:0;overflow-wrap:anywhere}.example-timeline svg{width:15px;height:15px;flex:none}.example-timeline>button:focus-visible{outline:2px solid #7194f4;outline-offset:2px}
''')
