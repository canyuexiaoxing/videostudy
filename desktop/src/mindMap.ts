export type MindMapEvidence = {
  sourceType: 'transcript' | 'image'
  sourceId: string
  startMs: number
  endMs: number
  quote: string
}

export type MindMapNode = {
  id: string
  title: string
  startMs: number
  endMs: number
  evidenceRefs: MindMapEvidence[]
  children: MindMapNode[]
  details?: MindMapNode[]
}

export type MindMapResult = {
  status: 'completed' | 'empty' | 'failed'
  provider: string
  modelId: string
  promptVersion: string
  createdAt: string
  root: MindMapNode
  examples?: MindMapNode[] | null
  uncertainties?: string[] | null
}

export type CanvasNode = {
  data: { text: string; uid: string; _sourceId: string; expand: boolean }
  children: CanvasNode[]
}

export function toCanvasNode(node: MindMapNode, expandedDepth = Infinity, depth = 0): CanvasNode {
  return {
    data: { text: node.title, uid: node.id, _sourceId: node.id, expand: depth < expandedDepth },
    children: node.children.map(child => toCanvasNode(child, expandedDepth, depth + 1)),
  }
}

export async function mediaFingerprint(file: Pick<Blob, 'size' | 'slice'>): Promise<string> {
  const sampleBytes = 64 * 1024
  const first = new Uint8Array(await file.slice(0, sampleBytes).arrayBuffer())
  const last = new Uint8Array(await file.slice(Math.max(0, file.size - sampleBytes)).arrayBuffer())
  const bytes = new Uint8Array(8 + first.length + last.length)
  new DataView(bytes.buffer).setBigUint64(0, BigInt(file.size))
  bytes.set(first, 8)
  bytes.set(last, 8 + first.length)
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))
  return Array.from(digest, value => value.toString(16).padStart(2, '0')).join('')
}

export async function jumpToMindMapNode(
  node: MindMapNode,
  media: Pick<HTMLVideoElement, 'currentTime' | 'play'> | null,
): Promise<'playing' | 'paused' | 'missing_media' | 'no_evidence'> {
  const evidence = node.evidenceRefs[0]
  if (!evidence) return 'no_evidence'
  if (!media) return 'missing_media'
  media.currentTime = evidence.startMs / 1000
  try {
    await media.play()
    return 'playing'
  } catch {
    return 'paused'
  }
}

/** Keep concept structure on the canvas; retain complete explanations in details. */
export function compactKnowledgeMap(root: MindMapNode): MindMapNode {
  const caseText=(text:string)=>/(?<!基)本题|该题|这道题|这一道题|这一题|这个题|当前题|(?<!基)本例|此例|^(?:例题|习题|练习题)\s*(?:[:：0-9一二三四五六七八九十]|$)/.test(text)
  function clean(node:MindMapNode,depth:number):MindMapNode|null {
    if(depth>0&&caseText(node.title))return null
    let children=node.children.map(child=>clean(child,depth+1)).filter((n):n is MindMapNode=>!!n)
    let details=(node.details??[]).map(child=>clean(child,depth+1)).filter((n):n is MindMapNode=>!!n)
    let refs=node.evidenceRefs.filter(ref=>!caseText(ref.quote))
    if(!refs.length)refs=children.flatMap(child=>child.evidenceRefs).concat(details.flatMap(child=>child.evidenceRefs))
    if(depth>0&&!refs.length)return null
    if(node.details == null&&depth>=2&&children.length&&node.children.every(child=>!child.children.length)){
      // Short named rules/formulas are independent concepts, even if leaves.
      // Sentence descriptions and conditions belong in their parent's details.
      const standalone=(child:MindMapNode)=>! /^(?:符号含义|适用条件|应用条件|操作步骤|注意事项|步骤[一二三四五六七八九十0-9：:]|易错点|公式内容)/.test(child.title)
      details=details.concat(children.filter(child=>!standalone(child)))
      children=children.filter(standalone)
    }
    const unique=[...new Map(refs.map(ref=>[ref.sourceId,{...ref}])).values()].sort((a,b)=>a.startMs-b.startMs)
    return {...node,evidenceRefs:unique,startMs:unique[0]?.startMs??0,endMs:Math.max(0,...unique.map(ref=>ref.endMs)),children,details}
  }
  return clean(root,0)!
}
