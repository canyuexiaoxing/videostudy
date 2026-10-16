export type PersonSelectionMode = 'off' | 'adjacent'
type ReadStore = Pick<Storage, 'getItem'>
type WriteStore = Pick<Storage, 'setItem'>
const key = (fingerprint: string) => `videoPersonSelection:v1:${fingerprint}`
export function loadPersonSelection(storage: ReadStore, fingerprint: string): PersonSelectionMode {
  if (!fingerprint) return 'off'
  try { return storage.getItem(key(fingerprint)) === 'adjacent' ? 'adjacent' : 'off' } catch { return 'off' }
}
export function savePersonSelection(storage: WriteStore, fingerprint: string, mode: PersonSelectionMode) {
  if (!fingerprint) return
  try { storage.setItem(key(fingerprint), mode) } catch { /* Current selection still works without storage. */ }
}
