type Cue = { startMs: number; endMs: number; text: string }

export type SubtitleSegment = Cue & { id: string }
export type SubtitleTarget = 'source' | 'zh' | 'en'
export type SubtitleMode = 'original' | 'ai'
export type SubtitleChange = {
  segmentId: string; originalText: string; text: string; reason: string
  evidence: { sourceFrameTimeMs: number; text: string }[]
}
export type SubtitleJob = {
  id: string
  status: 'awaiting_source' | 'queued' | 'processing' | 'completed' | 'partial' | 'failed' | 'unsupported' | 'not_requested'
  result?: {
    sourceLanguage: string; targetLanguage: string; mode: 'correction' | 'translation'
    segments: SubtitleSegment[]; changes: SubtitleChange[]; rejectedCount: number; concerns: string[]
  } | null
  error?: string | null
}

export function selectSubtitleSource(original: SubtitleSegment[], sourceLanguage: string,
  job: SubtitleJob | null, preferredMode: SubtitleMode) {
  const available = !!job?.result?.segments?.length && ['completed', 'partial'].includes(job.status)
  return preferredMode === 'ai' && available
    ? { segments: job!.result!.segments, language: job!.result!.targetLanguage, mode: 'ai' as const }
    : { segments: original, language: sourceLanguage || 'und', mode: 'original' as const }
}

export function setSubtitleVisibility(player: { textTracks: ArrayLike<{ mode: string }> } | null, enabled: boolean) {
  if (player?.textTracks[0]) player.textTracks[0].mode = enabled ? 'showing' : 'hidden'
}

export class SubtitleRequestError extends Error {
  status: number
  constructor(status: number) { super(`HTTP ${status}`); this.status = status }
}

export function createSubtitlePoller(options: {
  fetchJob: (id: string, target: SubtitleTarget, signal: AbortSignal) => Promise<SubtitleJob>
  onJob: (job: SubtitleJob) => void
  onError: (message: string) => void
  intervalMs?: number
  retryDelayMs?: number
}) {
  let generation = 0
  let controller: AbortController | null = null
  let timer: ReturnType<typeof setTimeout> | null = null
  function stop() {
    generation++
    controller?.abort()
    controller = null
    if (timer !== null) clearTimeout(timer)
    timer = null
  }
  async function query(id: string, target: SubtitleTarget, token: number, signal: AbortSignal, failures = 0) {
    try {
      const job = await options.fetchJob(id, target, signal)
      if (token !== generation || signal.aborted) return
      options.onJob(job)
      if (['awaiting_source', 'queued', 'processing'].includes(job.status)) {
        timer = setTimeout(() => { void query(id, target, token, signal) }, options.intervalMs ?? 2000)
      }
    } catch (cause) {
      if (token !== generation || signal.aborted) return
      const permanent = cause instanceof SubtitleRequestError && cause.status >= 400 && cause.status < 500
        && ![408, 429].includes(cause.status)
      if (!permanent && failures < 2) {
        timer = setTimeout(() => { void query(id, target, token, signal, failures + 1) },
          (options.retryDelayMs ?? 1000) * 2 ** failures)
        return
      }
      options.onError(cause instanceof Error ? cause.message : String(cause))
    }
  }
  function start(id: string, target: SubtitleTarget) {
    stop()
    controller = new AbortController()
    return query(id, target, generation, controller.signal)
  }
  return { start, stop }
}

function timestamp(milliseconds: number) {
  const ms = Math.round(milliseconds)
  return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}.${String(ms % 1000).padStart(3, '0')}`
}

export function toWebVtt(segments: Cue[]): string {
  return 'WEBVTT\n\n' + segments.filter(s => Number.isFinite(s.startMs) && Number.isFinite(s.endMs)
    && s.startMs >= 0 && s.endMs > s.startMs && s.text.trim()).map((s, i) => {
    const text = s.text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\r\n?/g, '\n').replace(/\n\s*\n/g, '\n')
    return `${i + 1}\n${timestamp(s.startMs)} --> ${timestamp(s.endMs)}\n${text}\n\n`
  }).join('')
}
