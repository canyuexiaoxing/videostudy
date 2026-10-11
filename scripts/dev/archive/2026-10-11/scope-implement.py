from pathlib import Path
root=Path(r'E:\workp\videostudy')
(root/'desktop/src/practiceScope.ts').write_text('''export type ScopeNode = { id: string; title: string; children?: ScopeNode[] }
function leafCount(node: ScopeNode): number {
  return node.children?.length ? node.children.reduce((sum, child) => sum + leafCount(child), 0) : 1
}
export function practiceScopes(root?: ScopeNode | null): ScopeNode[] {
  const scopes: ScopeNode[] = []
  function walk(node: ScopeNode) {
    if (node.children?.length && leafCount(node) > 1) scopes.push(node)
    node.children?.forEach(walk)
  }
  root?.children?.forEach(walk)
  return scopes
}
export function resolvePracticeScope(root?: ScopeNode | null, selectedId?: string): string {
  if (!root || !selectedId || selectedId === root.id) return ''
  const path: ScopeNode[] = []
  function find(node: ScopeNode): boolean {
    path.push(node)
    if (node.id === selectedId) return true
    if (node.children?.some(find)) return true
    path.pop()
    return false
  }
  if (!find(root)) return ''
  for (let index = path.length - 1; index > 0; index--) {
    const node = path[index]
    if (node.children?.length && leafCount(node) > 1) return node.id
  }
  return ''
}
''',encoding='utf-8')
p=root/'desktop/src/AiPractice.vue';s=p.read_text(encoding='utf-8')
s=s.replace("import StudyIcon from './StudyIcon.vue'", "import StudyIcon from './StudyIcon.vue'\nimport { practiceScopes, resolvePracticeScope } from './practiceScope'")
s=s.replace("const nodes=computed(()=>{const list:Node[]=[];function walk(n:Node){list.push(n);n.children?.forEach(walk)};props.mindMap?.root.children?.forEach(walk);return list})", "const nodes=computed(()=>practiceScopes(props.mindMap?.root))")
s=s.replace("watch(()=>props.selectedNodeId,id=>{if(id)scope.value=id})", "watch(()=>props.selectedNodeId,id=>{if(id)scope.value=resolvePracticeScope(props.mindMap?.root,id)})\nwatch(()=>props.mindMap?.root,root=>{scope.value=resolvePracticeScope(root,props.selectedNodeId||scope.value)})")
s=s.replace("   <label>练习范围", "   <label>练习范围")
# Hint describes the actual scope rather than exposing internal leaf mechanics.
s=s.replace('  <div v-else-if="!questions.length"', '  <p class="practice-intro">按完整知识分支练习，包含下级公式、条件和易错点。</p>\n  <div v-else-if="!questions.length"') if False else s
p.write_text(s,encoding='utf-8')
p=root/'backend-java/src/main/java/cn/videostudy/api/PracticeController.java';s=p.read_text(encoding='utf-8')
anchor='    private static void flatten(MindMapNode node,List<MindMapNode> nodes){'
helper='''    private static int leafCount(MindMapNode node) {
        if(node.children()==null||node.children().isEmpty())return 1;
        return node.children().stream().mapToInt(PracticeController::leafCount).sum();
    }
    private static boolean scopePath(MindMapNode node,String id,List<MindMapNode> path) {
        path.add(node);
        if(node.id().equals(id))return true;
        if(node.children()!=null)for(var child:node.children())if(scopePath(child,id,path))return true;
        path.removeLast();return false;
    }
    static MindMapNode practiceScope(MindMapNode root,String id) {
        if(id==null||id.isBlank())return root;
        var path=new ArrayList<MindMapNode>();
        if(!scopePath(root,id,path))throw new IllegalArgumentException("unknown_mindmap_node");
        for(int i=path.size()-1;i>0;i--){var node=path.get(i);if(node.children()!=null&&!node.children().isEmpty()&&leafCount(node)>1)return node;}
        return root;
    }
'''
assert anchor in s;s=s.replace(anchor,helper+anchor)
s=s.replace('var root=result.mindMap().root();var chosen=request.nodeId()==null||request.nodeId().isBlank()?root:find(root,request.nodeId());','var root=result.mindMap().root();var chosen=practiceScope(root,request.nodeId());')
s=s.replace('Objects.toString(request.nodeId(),"")', 'source.get("scopeNodeId")')
s=s.replace(':mindmap-practice-v1',':mindmap-practice-v2')
s=s.replace('request.nodeId()==null||request.nodeId().isBlank()?"整课知识点":find(result.mindMap().root(),request.nodeId()).title()', 'result.mindMap().root().id().equals(source.get("scopeNodeId"))?"整课知识点":(String)source.get("scopeTitle")')
s=s.replace('return Map.of("nodes",nodes,"pages",pages,"count",','return Map.of("scopeNodeId",chosen.id(),"scopeTitle",chosen.title(),"nodes",nodes,"pages",pages,"count",')
p.write_text(s,encoding='utf-8')
p=root/'agent-python/mind_map.py';s=p.read_text(encoding='utf-8').replace('grounded-mind-map-v5-teaching-evidence','grounded-mind-map-v6-case-guards')
anchor='def _node(node_id: str'
helper='''def _case_specific(text: str) -> bool:
    return bool(re.search(r"本题|该题|这道题|这一道题|这一题|这个题|当前题|本例|此例|^(?:例题|习题|练习题)\\s*(?:[:：0-9一二三四五六七八九十]|$)", text))


'''
assert anchor in s;s=s.replace(anchor,helper+anchor)
s=s.replace("            def is_example(raw):\n                if raw.get('kind') == 'knowledge': return False", "            def is_example(raw):\n                if _case_specific(str(raw.get('title', ''))): return True\n                if raw.get('kind') == 'knowledge': return False")
s=s.replace("                if is_example(raw):\n                    candidates.append(raw)","                if is_example(raw):\n                    for sid in raw.get('sourceIds', []) if isinstance(raw.get('sourceIds'), list) else []:\n                        if isinstance(sid, str) and sid in sources:\n                            example_ids.add(sid); teaching_ids.discard(sid)\n                    candidates.append(raw)")
s=s.replace("refs = [ref for ref in node['evidenceRefs'] if (ref['sourceId']", "refs = [ref for ref in node['evidenceRefs'] if not _case_specific(ref['quote']) and (ref['sourceId']")
s=s.replace('"Only teachingSourceIds may support core leaves; a node-level new_knowledge label is not proof. "','"Only teachingSourceIds may support core leaves; a node-level new_knowledge label is not proof. "\n        "Core titles and citations must not be tied to 本题/这道题 or specific question answers. Do not turn case commentary "\n        "into a general-looking title; retain it in examples. Group formulas, conditions and pitfalls into complete topics. "')
p.write_text(s,encoding='utf-8')
