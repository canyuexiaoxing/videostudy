export type BindingState = 'matched' | 'mismatch' | 'unverified'
export function mediaBindingState(metadata: string | null, size: number, fingerprint: string): BindingState {
  try {
    const saved = metadata ? JSON.parse(metadata) : null
    const valid = (value: unknown): value is string => typeof value === 'string' && /^[a-f0-9]{64}$/i.test(value)
    if (!saved || !Number.isSafeInteger(saved.size) || saved.size < 0 || !valid(saved.fingerprint) || !valid(fingerprint)) return 'unverified'
    return saved.size === size && saved.fingerprint.toLowerCase() === fingerprint.toLowerCase() ? 'matched' : 'mismatch'
  } catch { return 'unverified' }
}
export type RequestTicket = { signal: AbortSignal; current: () => boolean }
export function latestRequests() {
  let version = 0
  let controller: AbortController | null = null
  const invalidate = () => { version++; controller?.abort(); controller = null }
  return { invalidate, begin(): RequestTicket {
    invalidate(); const revision = version; controller = new AbortController(); const signal = controller.signal
    return { signal, current: () => revision === version && !signal.aborted }
  } }
}
