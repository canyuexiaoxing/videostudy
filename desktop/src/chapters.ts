export type VideoChapter = { id: string; title: string; startMs: number; endMs: number; sourceSegmentId?: string }
export function timelineChapters(source: VideoChapter[], durationSeconds: number): VideoChapter[] {
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) return []
  const durationMs = durationSeconds * 1000
  const chapters = source.filter(c => Number.isFinite(c.startMs) && c.startMs >= 0 && c.startMs < durationMs)
    .sort((a,b) => a.startMs-b.startMs).filter((c,i,a) => i===0 || c.startMs>a[i-1]!.startMs)
  return chapters.map((c,i) => ({...c,startMs:i===0?0:c.startMs,endMs:chapters[i+1]?.startMs??durationMs}))
}
export function chapterAt(chapters: VideoChapter[], timeMs: number) {
  return chapters.find(c => timeMs >= c.startMs && timeMs < c.endMs) ?? chapters.at(-1)
}
export function timeAtPointer(clientX: number, left: number, width: number, duration: number) {
  return width>0 && Number.isFinite(duration) && duration>0 ? Math.min(1,Math.max(0,(clientX-left)/width))*duration : 0
}
