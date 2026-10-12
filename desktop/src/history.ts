export type HistoryStatus = 'unknown' | 'queued' | 'processing' | 'completed' | 'failed' | 'expired'
export type HistoryEntry = { id: string; name: string; addedAt: string; status: HistoryStatus }
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export function serverHistory(value: unknown, cached: HistoryEntry[]): HistoryEntry[] {
  if (!Array.isArray(value)) throw new Error('历史列表格式异常')
  const seen = new Set<string>()
  return value.map(row => {
    if (!row || !uuid.test(row.id) || seen.has(row.id) ||
        !['queued','processing','completed','failed','expired'].includes(row.status) ||
        typeof row.createdAt !== 'string' || !Number.isFinite(Date.parse(row.createdAt)) ||
        !(row.name === null || typeof row.name === 'string')) throw new Error('历史列表格式异常')
    seen.add(row.id)
    const previous = cached.find(item => item.id === row.id)
    return {id: row.id, name: row.name?.trim() || previous?.name || `历史分析 · ${row.id.slice(0,8)}`,
      addedAt: row.createdAt, status: row.status as HistoryStatus}
  })
}
