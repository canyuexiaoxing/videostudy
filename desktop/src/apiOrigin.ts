/** Browser development keeps the legacy local service; Electron supplies its private port. */
export let API_ORIGIN = 'http://127.0.0.1:18080'
export function disableApiOrigin(): void { API_ORIGIN = 'http://127.0.0.1:0' }
export function setApiOrigin(value: unknown): boolean {
  if (typeof value !== 'string') return false
  try {
    const url = new URL(value)
    if (url.protocol !== 'http:' || !['127.0.0.1', '[::1]', 'localhost'].includes(url.hostname) || !url.port || Number(url.port) <= 0 || url.username || url.password || url.pathname !== '/' || url.search || url.hash) return false
    API_ORIGIN = url.origin
    return true
  } catch { return false }
}
