type Cue = { startMs: number; endMs: number; text: string }

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
