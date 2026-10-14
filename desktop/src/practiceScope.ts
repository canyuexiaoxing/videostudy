export type ScopeNode = { id: string; title: string; children?: ScopeNode[]; details?: ScopeNode[] }
function leafCount(node: ScopeNode): number {
  return node.children?.length ? node.children.reduce((sum, child) => sum + leafCount(child), 0) : 1
}
export function practiceScopes(root?: ScopeNode | null): ScopeNode[] {
  const scopes: ScopeNode[] = []
  function walk(node: ScopeNode) {
    if (node.details?.length || node.children?.length && leafCount(node) > 1) scopes.push(node)
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
    if (node.children?.some(find) || node.details?.some(find)) return true
    path.pop()
    return false
  }
  if (!find(root)) return ''
  for (let index = path.length - 1; index > 0; index--) {
    const node = path[index]
    if (node.details?.length || node.children?.length && leafCount(node) > 1) return node.id
  }
  return ''
}

/** Keep module hierarchy, skipping detail-only and ineligible singleton branches. */
export function practiceScopeTree(root?: ScopeNode | null): ScopeNode[] {
  const selectable = new Set(practiceScopes(root).map(node => node.id))
  root?.children?.forEach(node => selectable.add(node.id))
  function branches(node: ScopeNode): ScopeNode[] {
    const children = (node.children ?? []).flatMap(branches)
    return selectable.has(node.id) ? [{ ...node, children, details: undefined }] : children
  }
  return (root?.children ?? []).flatMap(branches)
}
