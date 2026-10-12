# Historical one-time edit script. Do not rerun against the completed implementation.
from pathlib import Path
root=Path(__file__).resolve().parents[2]
p=root/'backend-java/src/main/resources/db/migration/V12__history_filename.sql'
p.write_text("ALTER TABLE transcription_jobs ADD COLUMN original_filename VARCHAR(255) NULL;\n",encoding='utf-8')
p=root/'backend-java/src/main/java/cn/videostudy/api/TranscriptionJobStore.java';s=p.read_text()
anchor='    public IgnoreRegion findIgnoredRegion(String id) {'
addition="""    public record HistoryItem(String id, String name, String status, Instant createdAt) {}

    public void saveOriginalFilename(String id, String filename) {
        var name = filename == null ? "" : filename.replace((char)92, (char)47);
        name = name.substring(name.lastIndexOf('/') + 1).replaceAll("[\\p{Cntrl}]", "").strip();
        if (name.length() > 255) name = name.substring(0, 255);
        requireOne(jdbc.update("UPDATE transcription_jobs SET original_filename = ? WHERE id = ?",
            name.isEmpty() ? null : name, id));
    }

    public List<HistoryItem> listHistory() {
        return jdbc.query("SELECT id, original_filename, status, created_at FROM transcription_jobs ORDER BY created_at DESC, id DESC",
            (row, number) -> new HistoryItem(row.getString("id"), row.getString("original_filename"),
                row.getString("status"), row.getTimestamp("created_at").toInstant()));
    }

"""
assert anchor in s;s=s.replace(anchor,addition+anchor);p.write_text(s,encoding='utf-8')
p=root/'backend-java/src/main/java/cn/videostudy/api/TranscriptionController.java';s=p.read_text()
s=s.replace('            if (aiSubtitles && subtitles != null)', '            store.saveOriginalFilename(id, file.getOriginalFilename());\n            if (aiSubtitles && subtitles != null)')
s=s.replace('    @GetMapping("/{id}")','    @GetMapping\n    public List<TranscriptionJobStore.HistoryItem> history() { return store.listHistory(); }\n\n    @GetMapping("/{id}")',1);p.write_text(s,encoding='utf-8')
p=root/'desktop/src/history.ts';p.write_text("""export type HistoryStatus = 'unknown' | 'queued' | 'processing' | 'completed' | 'failed' | 'expired'
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
""",encoding='utf-8')
p=root/'desktop/src/App.vue';s=p.read_text()
s=s.replace('nextTick, onUnmounted','nextTick, onMounted, onUnmounted')
s=s.replace("type HistoryStatus = 'unknown' | 'queued' | 'processing' | 'completed' | 'failed'\ntype HistoryEntry = { id: string; name: string; addedAt: string; status: HistoryStatus }", "import {serverHistory} from './history'\nimport type {HistoryStatus, HistoryEntry} from './history'")
s=s.replace("['unknown', 'queued', 'processing', 'completed', 'failed'].includes(item.status)","['unknown', 'queued', 'processing', 'completed', 'failed', 'expired'].includes(item.status)")
s=s.replace("const historyError = ref('')","""const historyError = ref('')
const historyLoading = ref(false), historySynced = ref(false)
let historyController:AbortController|null = null, historyGeneration = 0
function cacheHistory(){try{localStorage.setItem('analysisHistory:v1',JSON.stringify(analysisHistory.value))}catch{/* Keep server results when storage is unavailable. */}}
async function refreshHistory(){
 if(deletingHistoryId.value)return
 const generation=++historyGeneration
 historyController?.abort();const controller=new AbortController();historyController=controller;historyLoading.value=true
 try{
  const response=await fetch(`${apiBase}/transcriptions`,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])})
  if(!response.ok)throw new Error(`HTTP ${response.status}`)
  const data=await response.json()
  if(controller.signal.aborted||generation!==historyGeneration)return
  const cached=analysisHistory.value.map(item=>({...item,name:savedMediaName(item.id)||item.name}))
  analysisHistory.value=serverHistory(data,cached);historySynced.value=true;historyError.value='';cacheHistory()
 }catch(e){if(!controller.signal.aborted&&generation===historyGeneration)historyError.value='无法同步服务器历史，当前显示上次缓存。请稍后刷新。'}
 finally{if(generation===historyGeneration){historyLoading.value=false;historyController=null}}
}
watch(rightTab,tab=>{if(tab==='history')void refreshHistory()})
let historyTimer:ReturnType<typeof setInterval>|undefined
function focusHistory(){void refreshHistory()}
onMounted(()=>{void refreshHistory();window.addEventListener('focus',focusHistory);historyTimer=setInterval(()=>{if(rightTab.value==='history'&&!document.hidden&&!historyLoading.value)void refreshHistory()},15000)})
onUnmounted(()=>{++historyGeneration;historyController?.abort();clearInterval(historyTimer);window.removeEventListener('focus',focusHistory)})
""")
s=s.replace("localStorage.setItem('analysisHistory:v1', JSON.stringify(analysisHistory.value))",'cacheHistory()')
s=s.replace("completed: '已完成', failed: '失败'", "completed: '已完成', failed: '失败', expired: '已过期'")
s=s.replace("  deletingHistoryId.value = entry.id", "  ++historyGeneration;historyController?.abort();historyLoading.value=false\n  deletingHistoryId.value = entry.id")
s=s.replace("    deletingHistoryId.value = ''\n", "    deletingHistoryId.value = ''\n    void refreshHistory()\n")
s=s.replace('<h3>本机历史</h3>','<h3>分析历史</h3>')
s=s.replace('<p v-if="historyError" class="history-error" role="alert">', '<button type="button" class="text-link" :disabled="historyLoading || !!deletingHistoryId" @click="refreshHistory">{{ historyLoading ? \'同步中…\' : \'刷新历史\' }}</button>\n        <p v-if="historyError" class="history-error" role="alert">')
s=s.replace('上次状态：{{ historyStatusLabel(entry.status) }}','{{ historyStatusLabel(entry.status) }}').replace('加入本机 {{ formatHistoryDate(entry.addedAt) }}','创建于 {{ formatHistoryDate(entry.addedAt) }}')
s=s.replace('<div v-else class="sidebar-empty compact"><h3>还没有历史记录</h3><p>第一次分析或按编号读取结果后，记录会出现在这里。</p></div>', '<div v-else class="sidebar-empty compact"><h3>{{ historyLoading ? \'正在读取历史记录\' : historySynced ? \'还没有历史记录\' : \'尚未读取到历史记录\' }}</h3><p>分析记录由服务器统一保存。</p></div>')
s=s.replace('此列表只保存在当前设备。清除浏览器数据会清空列表，但不会自动删除服务器上的分析结果。', '历史列表从当前服务同步，清除浏览器缓存后仍可恢复。删除记录会同时清理服务器分析结果、截图及关联练习。')
p.write_text(s,encoding='utf-8')
