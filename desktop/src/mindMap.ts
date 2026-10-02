export type MindMapEvidence = {
  sourceType: 'transcript'
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
}

export type MindMapResult = {
  status: 'completed' | 'empty' | 'failed'
  provider: string
  modelId: string
  promptVersion: string
  createdAt: string
  root: MindMapNode
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
