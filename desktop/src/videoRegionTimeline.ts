import { normalizeRegion } from './videoRegion.ts'
import type { VideoRegion } from './videoRegion.ts'
export type RegionNode = { timeMs: number; region: VideoRegion | null }
export type IgnoreSetting = VideoRegion | { nodes: RegionNode[] }
export function normalizeIgnoreSetting(value: unknown, allowFull=false): IgnoreSetting | null {
  if (!value || typeof value !== 'object') return null
  if ('nodes' in value) {
    const raw = (value as {nodes: unknown}).nodes
    if (!Array.isArray(raw) || !raw.length || raw.length > 200 || Object.keys(value).length !== 1) return null
    const nodes: RegionNode[] = []
    for (const item of raw) {
      if (!item || typeof item !== 'object' || Object.keys(item).length !== 2 || !Number.isSafeInteger(item.timeMs) || item.timeMs < 0 || (!nodes.length ? item.timeMs !== 0 : item.timeMs <= nodes[nodes.length - 1].timeMs)) return null
      const region = item.region === null ? null : normalizeRegion(item.region)
      if (item.region !== null && (!region || region.width * region.height > (allowFull?1:.95))) return null
      nodes.push({timeMs: item.timeMs, region})
    }
    return {nodes}
  }
  const region = normalizeRegion(value)
  return region && region.width * region.height <= (allowFull?1:.95) ? region : null
}
export function regionNodes(setting: IgnoreSetting | null): RegionNode[] {
  return !setting ? [] : 'nodes' in setting ? setting.nodes : [{timeMs: 0, region: setting}]
}
export function regionAt(setting: IgnoreSetting | null, timeMs: number): VideoRegion | null {
  let region: VideoRegion | null = null
  for (const node of regionNodes(setting)) { if (node.timeMs > timeMs) break; region = node.region }
  return region
}
export function upsertRegionNode(setting: IgnoreSetting | null, timeMs: number, region: VideoRegion | null, allowFull=false): IgnoreSetting {
  const nodes = regionNodes(setting).map(node => ({...node}))
  const time = nodes.length ? timeMs : 0
  if (!Number.isSafeInteger(time) || time < 0) throw new Error('节点时间无效')
  const index = nodes.findIndex(node => node.timeMs === time)
  if (index >= 0) nodes[index] = {timeMs: time, region}
  else nodes.push({timeMs: time, region})
  nodes.sort((a, b) => a.timeMs - b.timeMs)
  const normalized = normalizeIgnoreSetting({nodes},allowFull)
  if (!normalized) throw new Error('最多保存 200 个节点，请检查区域或删除多余节点')
  return normalized
}
export function removeRegionNode(setting: IgnoreSetting | null, timeMs: number): IgnoreSetting | null {
  if (timeMs === 0) return setting
  const nodes = regionNodes(setting).filter(node => node.timeMs !== timeMs)
  return nodes.length ? {nodes} : null
}

export function validateRegionCombination(analysis: IgnoreSetting | null, ignored: IgnoreSetting | null): void {
  const times = new Set([0, ...regionNodes(analysis).map(n => n.timeMs), ...regionNodes(ignored).map(n => n.timeMs)])
  for (const time of times) {
    const a = regionAt(analysis, time), b = regionAt(ignored, time)
    if (a && b && b.x <= a.x && b.y <= a.y && b.x+b.width >= a.x+a.width && b.y+b.height >= a.y+a.height)
      throw new Error(`忽略框在 ${Math.floor(time/1000)} 秒覆盖了整个分析区域，请调整区域或时间节点`)
  }
}
