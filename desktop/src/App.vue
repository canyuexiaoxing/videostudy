<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import MindMapCanvas from './MindMapCanvas.vue'
import MindMapDialog from './MindMapDialog.vue'
import StudyIcon from './StudyIcon.vue'
import ChapterPlayer from './ChapterPlayer.vue'
import AnalysisProgressBar from './AnalysisProgress.vue'
import type { AnalysisProgress } from './analysisProgress'
import VideoWorkspace from './VideoWorkspace.vue'
import { normalizeIgnoreSetting } from './videoRegionTimeline'
import type { IgnoreSetting } from './videoRegionTimeline'
import SubtitleSettings from './SubtitleSettings.vue'
import AiOverview from './AiOverview.vue'
import AiPractice from './AiPractice.vue'
import PageGallery from './PageGallery.vue'
import { appearanceCss, normalizeAppearance, positionCue } from './subtitleAppearance'
import type { VideoChapter } from './chapters'
import { createSubtitlePoller, needsSubtitleUpdate, selectSubtitleSource, setSubtitleVisibility, SubtitleRequestError, toWebVtt } from './subtitles'
import type { SubtitleJob, SubtitleMode, SubtitleTarget } from './subtitles'
import { jumpToMindMapNode, mediaFingerprint } from './mindMap'
import { mediaBindingState, latestRequests } from './mediaBinding'
import type { RequestTicket } from './mediaBinding'
import type { MindMapNode as MindNode, MindMapResult } from './mindMap'

type Segment = { id: string; startMs: number; endMs: number; text: string }
type OcrBlock = { text: string; score: number; polygon: number[][] }
type ImageAnalysis = { status: string; title: string; content: string; visualElements: string[]; uncertainties: string[] }
type VisualEvidence = { frameTimeMs: number; ocrBlocks: OcrBlock[]; imageAnalysis?: ImageAnalysis }
type OcrLine = { text: string; sourceFrameTimeMs: number; sourceBlockIndex: number }
type PageGroup = { pageIndex: number; firstFrameTimeMs: number; lastFrameTimeMs: number;
  memberFrameTimesMs: number[]; representativeFrameTimesMs: number[];
  decision: string; decisionReason: string; ocrLines: OcrLine[]; imageAnalysis?: ImageAnalysis; textAnalysis?: ImageAnalysis }
type Review = { status: string; resampledTimesMs: number[]; concerns: string[] }
type TranscriptionJob = { id: string; status: string; progress?: AnalysisProgress | null; result?: { language: string; segments: Segment[]; visualEvidence?: VisualEvidence[]; pageGroups?: PageGroup[]; mindMap?: MindMapResult; visualAnalysisMode?: 'ocr_only' | 'both'; ocrModelId?: string; imageModelId?: string; review?: Review }; error?: string }
type RightTab = 'map' | 'practice' | 'transcript' | 'slides' | 'notes' | 'history'
type StudyNote = { id: string; scope: string; timeMs: number; text: string; createdAt: string }
type HistoryStatus = 'unknown' | 'queued' | 'processing' | 'completed' | 'failed'
type HistoryEntry = { id: string; name: string; addedAt: string; status: HistoryStatus }

const jobIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function savedMediaName(id: string): string {
  try {
    const media = JSON.parse(localStorage.getItem(`analysisMedia:${id}`) ?? 'null')
    return typeof media?.name === 'string' ? media.name : ''
  } catch { return '' }
}

function readHistory(): HistoryEntry[] {
  let entries: HistoryEntry[] = []
  try {
    const saved = JSON.parse(localStorage.getItem('analysisHistory:v1') ?? '[]')
    if (Array.isArray(saved)) entries = saved.filter(item => jobIdPattern.test(item?.id) &&
      typeof item.name === 'string' && typeof item.addedAt === 'string' &&
      ['unknown', 'queued', 'processing', 'completed', 'failed'].includes(item.status))
  } catch { /* An invalid local list must not block the app. */ }
  const lastId = localStorage.getItem('lastAnalysisId') ?? ''
  const knownIds = new Set(entries.map(item => item.id))
  const oldIds = [lastId, ...Array.from({ length: localStorage.length }, (_, index) => localStorage.key(index) ?? '')
    .filter(key => key.startsWith('analysisMedia:')).map(key => key.slice('analysisMedia:'.length))]
  for (const id of oldIds) {
    if (!jobIdPattern.test(id) || knownIds.has(id)) continue
    entries.push({ id, name: savedMediaName(id) || '历史分析',
      addedAt: new Date().toISOString(), status: 'unknown' })
    knownIds.add(id)
  }
  return entries
}

function readStudyNotes(): StudyNote[] {
  try {
    const value = JSON.parse(localStorage.getItem('studyNotes:v1') ?? '[]')
    return Array.isArray(value) ? value.filter(note => typeof note.id === 'string' && typeof note.scope === 'string' && typeof note.text === 'string') : []
  } catch { return [] }
}

const apiBase = 'http://127.0.0.1:18080/api'
const video = ref<HTMLVideoElement | null>(null)
const transcriptList = ref<HTMLElement | null>(null)
const sidebarTranscriptList = ref<HTMLElement | null>(null)
const rightTab = ref<RightTab>('map')
const rightTabOrder: RightTab[] = ['map', 'practice', 'transcript', 'slides', 'notes', 'history']
const transcriptQuery = ref('')
const noteDraft = ref('')
const studyNotes = ref<StudyNote[]>(readStudyNotes())
const analysisHistory = ref<HistoryEntry[]>(readHistory())
const deletingHistoryId = ref('')
const historyError = ref('')
const selectedFile = ref<File | null>(null)
const selectedFingerprint = ref('')
const workspaceOpen = ref(false)
const ignoredRegion = ref<IgnoreSetting|null>(null)
const analysisRegion = ref<IgnoreSetting|null>(null)
watch(selectedFingerprint, fingerprint => {
  try { ignoredRegion.value = fingerprint ? normalizeIgnoreSetting(JSON.parse(localStorage.getItem(`videoIgnoreRegion:v1:${fingerprint}`) ?? 'null')) : null }
  catch { ignoredRegion.value = null }
  try { analysisRegion.value=fingerprint?normalizeIgnoreSetting(JSON.parse(localStorage.getItem(`videoAnalysisRegion:v1:${fingerprint}`)??'null'),true):null }catch {analysisRegion.value=null}
})
function saveIgnoredRegion(region: IgnoreSetting|null) {
  ignoredRegion.value = normalizeIgnoreSetting(region)
  if (!selectedFingerprint.value) return
  try {
    const key = `videoIgnoreRegion:v1:${selectedFingerprint.value}`
    if (ignoredRegion.value) localStorage.setItem(key, JSON.stringify(ignoredRegion.value))
    else localStorage.removeItem(key)
  } catch { /* Keep the current setting even when browser storage is unavailable. */ }
}
function saveAnalysisRegion(region:IgnoreSetting|null){
 analysisRegion.value=normalizeIgnoreSetting(region,true)
 if(!selectedFingerprint.value)return
 try{const key=`videoAnalysisRegion:v1:${selectedFingerprint.value}`;if(analysisRegion.value)localStorage.setItem(key,JSON.stringify(analysisRegion.value));else localStorage.removeItem(key)}catch{}
}
function openVideoWorkspace() { video.value?.pause(); workspaceOpen.value = true }

const selectionRequests = latestRequests()
const analysisRequests = latestRequests()
const mindMapRequests = latestRequests()
const checkingMedia = ref(false)
let changingAnalysisId = false
const videoUrl = ref('')
const compatibilityBusy = ref(false)
const compatibilityMessage = ref('')
const compatibilityId = ref('')
const compatibilityActive = ref(false)
let originalVideoUrl = ''
let compatibilityGeneration = 0
let compatibilityUpload: XMLHttpRequest | null = null

function clearCompatibility() {
  compatibilityGeneration++
  compatibilityUpload?.abort()
  compatibilityUpload = null
  const id = compatibilityId.value
  compatibilityId.value = ''
  compatibilityBusy.value = false
  compatibilityActive.value = false
  compatibilityMessage.value = ''
  if (originalVideoUrl && originalVideoUrl !== videoUrl.value) URL.revokeObjectURL(originalVideoUrl)
  originalVideoUrl = ''
  if (id) void fetch(`${apiBase}/compatibility/${id}`, { method: 'DELETE', keepalive: true }).catch(() => {})
}
watch(selectedFile, clearCompatibility, { flush: 'sync' })

async function switchPlayback(src: string) {
  const player = video.value
  const state = player ? { time: player.currentTime, paused: player.paused, volume: player.volume,
    muted: player.muted, rate: player.playbackRate } : null
  player?.pause()
  videoUrl.value = src
  await nextTick()
  const target = video.value
  if (!target || !state) return
  const restore = () => {
    if (videoUrl.value !== src) return
    target.currentTime = Math.min(state.time, target.duration || state.time)
    target.volume = state.volume; target.muted = state.muted; target.playbackRate = state.rate
    if (!state.paused) void target.play().catch(() => { compatibilityMessage.value = '兼容视频已就绪，请点击播放' })
  }
  if (target.readyState >= 1) restore()
  else target.addEventListener('loadedmetadata', restore, { once: true })
}

async function generateCompatibility() {
  if (!selectedFile.value || compatibilityBusy.value) return
  if (compatibilityId.value && originalVideoUrl) {
    compatibilityActive.value = !compatibilityActive.value
    await switchPlayback(compatibilityActive.value ? `${apiBase}/compatibility/${compatibilityId.value}/video` : originalVideoUrl)
    compatibilityMessage.value = compatibilityActive.value ? '正在使用 H.264 兼容副本' : '正在使用原视频'
    return
  }
  const file = selectedFile.value
  const generation = ++compatibilityGeneration
  compatibilityBusy.value = true
  compatibilityMessage.value = '正在检查后台显卡编码能力…'
  try {
    const capabilityResponse = await fetch(`${apiBase}/compatibility/capabilities`)
    if (!capabilityResponse.ok) throw new Error('无法连接后台显卡转码服务')
    const capability = await capabilityResponse.json()
    if (generation !== compatibilityGeneration) return
    if (!capability.available) throw new Error(capability.error || '后台显卡编码不可用')
    const job: { id: string } = await new Promise((resolve, reject) => {
      const request = new XMLHttpRequest()
      compatibilityUpload = request
      request.open('POST', `${apiBase}/compatibility`)
      request.responseType = 'json'
      request.upload.onprogress = event => {
        if (generation === compatibilityGeneration) compatibilityMessage.value = event.lengthComputable
          ? `上传用于转码：${Math.round(event.loaded / event.total * 100)}%` : '正在上传用于转码…'
      }
      request.onerror = () => reject(new Error('上传失败，请检查后台连接'))
      request.onabort = () => reject(new Error('已取消'))
      request.onload = () => request.status === 202 ? resolve(request.response) : reject(new Error('无法创建转码任务，显卡可能正在处理其他任务'))
      const form = new FormData(); form.append('file', file); request.send(form)
    })
    compatibilityUpload = null
    if (generation !== compatibilityGeneration) {
      void fetch(`${apiBase}/compatibility/${job.id}`, { method: 'DELETE' }); return
    }
    compatibilityId.value = job.id
    for (;;) {
      if (generation !== compatibilityGeneration) return
      const response = await fetch(`${apiBase}/compatibility/${job.id}`)
      if (!response.ok) throw new Error('查询转码状态失败')
      const result = await response.json()
      if (generation !== compatibilityGeneration) return
      if (result.status === 'failed') throw new Error(result.error || '显卡转码失败')
      if (result.status === 'completed') break
      compatibilityMessage.value = `显卡转码：${result.progress || 0}%（无需重新分析）`
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
    originalVideoUrl = videoUrl.value
    compatibilityActive.value = true
    await switchPlayback(`${apiBase}/compatibility/${job.id}/video`)
    compatibilityMessage.value = '正在使用 H.264 兼容副本（24 小时后自动清理）'
  } catch (cause) {
    if (generation === compatibilityGeneration) {
      compatibilityMessage.value = cause instanceof Error ? cause.message : '显卡转码失败'
      const id = compatibilityId.value; compatibilityId.value = ''
      if (id) void fetch(`${apiBase}/compatibility/${id}`, { method: 'DELETE' }).catch(() => {})
    }
  } finally {
    if (generation === compatibilityGeneration) compatibilityBusy.value = false
  }
}
const filename = ref('')
const analysisState = ref('')
const analysisProgress = ref<AnalysisProgress|null>(null)
const status = ref('请选择本地视频')
const transcript = ref<Segment[]>([])
const visualEvidence = ref<VisualEvidence[]>([])
const pageGroups = ref<PageGroup[]>([])
const mindMap = ref<MindMapResult | null>(null)
const selectedMindNode = ref<MindNode | null>(null)
const expandedMap = ref(false)
const activeSegmentId = ref('')
const generatingMindMap = ref(false)
const isAnalysisPending = ref(false)
const visualAnalysisMode = ref<'ocr_only' | 'both'>('both')
const coarseChangePercent = ref('2')
const coarseSampleSeconds = ref(2)
const advancedOpen = ref(false)
const review = ref<Review | null>(null)
const failedJobId = ref('')
const existingJobId = ref('')
watch([mindMap, selectedFile, existingJobId], () => { expandedMap.value = false })
const confirmedMedia = computed(() => !!selectedFile.value && !checkingMedia.value && !!existingJobId.value &&
  mediaBindingState(localStorage.getItem(`analysisMedia:${existingJobId.value}`), selectedFile.value.size, selectedFingerprint.value) === 'matched')
function setAnalysisId(id: string) {
  changingAnalysisId = true
  existingJobId.value = id
  changingAnalysisId = false
}
const error = ref('')
const unavailableFrames = ref<Set<number>>(new Set())
const currentPlaybackMs = ref(0)
const subtitleEnabled = ref(true)
const subtitleAppearance=ref(normalizeAppearance((()=>{try{return JSON.parse(localStorage.getItem('subtitleAppearance:v1')??'null')}catch{return null}})()))
const cueStyleElement=document.createElement('style')
document.head.append(cueStyleElement)
watch(subtitleAppearance,value=>{
  cueStyleElement.textContent=appearanceCss(value)
  try{localStorage.setItem('subtitleAppearance:v1',JSON.stringify(value))}catch{/* Storage may be unavailable. */}
  syncSubtitleVisibility()
},{deep:true,immediate:true})
const subtitleUrl = ref('')
const sourceLanguage = ref('und')
const videoChapters = ref<VideoChapter[]>([])
const chapterStatus = ref('not_requested')
let chapterController: AbortController | null = null
watch([existingJobId, () => transcript.value.length], async ([id, count]) => {
  chapterController?.abort()
  videoChapters.value = []
  chapterStatus.value = 'not_requested'
  if (!id || !count) return
  const controller = new AbortController()
  chapterController = controller
  let errors = 0
  try {
    for (let attempt = 0; attempt < 900 && !controller.signal.aborted; attempt++) {
      try {
        let response = await fetch(`${apiBase}/transcriptions/${id}/chapters`, { signal: controller.signal })
        if (!response.ok) throw new SubtitleRequestError(response.status)
        let job = await response.json()
        if (job.status === 'not_requested') {
          response = await fetch(`${apiBase}/transcriptions/${id}/chapters`, { method: 'POST', signal: controller.signal })
          if (!response.ok) throw new SubtitleRequestError(response.status)
          job = await response.json()
        }
        if (controller.signal.aborted) return
        errors = 0
        chapterStatus.value = job.status
        if (job.status === 'completed') { videoChapters.value = job.result?.chapters ?? []; return }
        if (job.status === 'failed') return
      } catch (cause) {
        if (controller.signal.aborted) return
        const permanent = cause instanceof SubtitleRequestError && cause.status >= 400 && cause.status < 500 && ![408,429].includes(cause.status)
        if (permanent || ++errors >= 3) throw cause
      }
      await new Promise(resolve => setTimeout(resolve, 1500))
    }
    if (!controller.signal.aborted) chapterStatus.value = 'failed'
  } catch { if (!controller.signal.aborted) chapterStatus.value = 'failed' }
})
onUnmounted(() => chapterController?.abort())
const subtitleTargetLanguage = ref<SubtitleTarget>('source')
const subtitleMode = ref<SubtitleMode>('original')
const subtitleJob = ref<SubtitleJob | null>(null)
const subtitleCourseId = ref('')
const subtitleRequestError = ref('')
const requestingSubtitles = ref(false)
let subtitleRequestGeneration = 0
const selectedSubtitles = computed(() => selectSubtitleSource(transcript.value, sourceLanguage.value, subtitleJob.value, subtitleMode.value))
const aiSubtitlesAvailable = computed(() => selectSubtitleSource(transcript.value, sourceLanguage.value, subtitleJob.value, 'ai').mode === 'ai')
const subtitleChanges = computed(() => subtitleJob.value?.result?.changes ?? [])
const subtitleChangeById = computed(() => new Map(subtitleChanges.value.map(change => [change.segmentId, change])))
const subtitleIsTranslation = computed(() => subtitleJob.value?.result?.mode === 'translation')
const subtitleNeedsUpdate = computed(() => needsSubtitleUpdate(subtitleJob.value))
const canGenerateSubtitles = computed(() => !!transcript.value.length && subtitleCourseId.value === existingJobId.value
  && ['not_requested', 'completed', 'partial', 'failed'].includes(subtitleJob.value?.status ?? '') && !isAnalysisPending.value && !requestingSubtitles.value)
const subtitleStatusMessage = computed(() => {
  if (!subtitleCourseId.value) return ''
  if (subtitleRequestError.value) return 'AI 字幕暂时不可用；原文仍可使用。'
  if (requestingSubtitles.value) return '正在提交 AI 字幕任务…'
  const target = subtitleTargetLanguage.value === 'en' ? '英文' : subtitleTargetLanguage.value === 'zh' ? '中文' : '同语言'
  switch (subtitleJob.value?.status) {
    case 'awaiting_source': return 'AI 字幕等待语音与课件分析；课程分析继续进行。'
    case 'queued': return `AI ${target}字幕排队中；原文可先使用。`
    case 'processing': return `正在生成 AI ${target}字幕；原文可先使用。`
    case 'partial': return 'AI 字幕部分完成；已通过校验的内容可使用，其余保留原文。'
    case 'completed': return subtitleIsTranslation.value ? `AI ${subtitleJob.value?.result?.targetLanguage === 'en' ? '英文' : '中文'}翻译字幕已生成。`
      : `AI 校正字幕已生成 · ${subtitleChanges.value.length} 处调整。`
    case 'failed': return 'AI 字幕生成失败；原文仍可使用。'
    case 'unsupported': return 'AI 字幕目前支持中文和英文；原文仍可使用。'
    case 'not_requested': return 'AI 字幕按需生成；点击“生成 AI 字幕”后才开始校正或翻译。'
    default: return '正在读取 AI 字幕状态…'
  }
})
const subtitlePoller = createSubtitlePoller({
  fetchJob: async (id, target, signal) => {
    const response = await fetch(`${apiBase}/transcriptions/${id}/subtitles?targetLanguage=${target}`, { signal })
    if (!response.ok) throw new SubtitleRequestError(response.status)
    return await response.json() as SubtitleJob
  },
  onJob: job => { subtitleJob.value = job; subtitleRequestError.value = '' },
  onError: message => { subtitleRequestError.value = message }
})

function clearSubtitleJob() {
  subtitleRequestGeneration++
  subtitlePoller.stop()
  subtitleCourseId.value = ''
  subtitleJob.value = null
  subtitleRequestError.value = ''
  requestingSubtitles.value = false
  subtitleMode.value = 'original'
}

function readSubtitleJob(id: string) {
  clearSubtitleJob()
  subtitleCourseId.value = id
  void subtitlePoller.start(id, subtitleTargetLanguage.value)
}

async function generateSubtitles() {
  if (!canGenerateSubtitles.value) return
  const id = subtitleCourseId.value
  const target = subtitleTargetLanguage.value
  const token = ++subtitleRequestGeneration
  requestingSubtitles.value = true
  subtitleRequestError.value = ''
  try {
    const response = await fetch(`${apiBase}/transcriptions/${id}/subtitles`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ targetLanguage: target,
        force: ['completed', 'partial'].includes(subtitleJob.value?.status ?? '') })
    })
    if (token !== subtitleRequestGeneration) return
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const job = await response.json() as SubtitleJob
    if (token !== subtitleRequestGeneration) return
    subtitleJob.value = job
    void subtitlePoller.start(id, target)
  } catch (cause) {
    if (token === subtitleRequestGeneration) subtitleRequestError.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    if (token === subtitleRequestGeneration) requestingSubtitles.value = false
  }
}

watch(subtitleTargetLanguage, () => {
  const id = subtitleCourseId.value
  if (id) {
    const mode=subtitleMode.value
    readSubtitleJob(id)
    subtitleMode.value=mode
  }
})
watch(existingJobId, (id, previous) => {
  if (!changingAnalysisId && id !== previous) {
    selectionRequests.invalidate()
    checkingMedia.value = false
    invalidateAnalysisRequests()
    clearLoadedAnalysis()
  }
  if (subtitleCourseId.value && id !== subtitleCourseId.value) clearSubtitleJob()
}, { flush: 'sync' })
function syncSubtitleVisibility() {
  setSubtitleVisibility(video.value, subtitleEnabled.value)
  const track = video.value?.textTracks[0]
  const cues = track?.cues
  const active = new Set(track?.activeCues ? Array.from(track.activeCues) : [])
  if (cues && track) for (const cue of Array.from(cues)) {
    if (cue instanceof VTTCue) {
      const changed=cue.snapToLines||cue.line!==subtitleAppearance.value.vertical
      positionCue(cue,subtitleAppearance.value)
      // Chromium may cache the active cue's layout while paused.
      if(changed&&active.has(cue)){track.removeCue(cue);track.addCue(cue)}
    }
  }
  if (video.value?.textTracks[0]) {
    video.value.textTracks.addEventListener('change', refreshSubtitleToggle)
  }
}
function refreshSubtitleToggle() {
  const track = video.value?.textTracks[0]
  if (track?.cues?.length) subtitleEnabled.value = track.mode === 'showing'
}
watch(() => selectedSubtitles.value.segments, segments => {
  if (subtitleUrl.value) URL.revokeObjectURL(subtitleUrl.value)
  subtitleUrl.value = segments.length ? URL.createObjectURL(new Blob([toWebVtt(segments)], { type: 'text/vtt;charset=utf-8' })) : ''
})
watch([subtitleEnabled, subtitleUrl, video], async () => {
  await nextTick()
  syncSubtitleVisibility()
})
watch(video, (_, previous) => previous?.textTracks.removeEventListener('change', refreshSubtitleToggle))
const activeSlide = computed(() => {
  if (!pageGroups.value.length) return null
  return [...pageGroups.value].reverse().find(page => page.firstFrameTimeMs <= currentPlaybackMs.value) ?? pageGroups.value[0]
})
const activeLegacyFrame = computed(() => {
  if (!visualEvidence.value.length) return null
  return [...visualEvidence.value].reverse().find(frame => frame.frameTimeMs <= currentPlaybackMs.value) ?? visualEvidence.value[0]
})
const filteredTranscript = computed(() => transcript.value.filter(segment => segment.text.includes(transcriptQuery.value.trim())))
const noteScopes = computed(() => transcript.value.length || mindMap.value
  ? [existingJobId.value, selectedFingerprint.value].filter(Boolean)
  : selectedFile.value ? [selectedFingerprint.value].filter(Boolean) : [])
const visibleNotes = computed(() => studyNotes.value.filter(note => noteScopes.value.includes(note.scope)).sort((a, b) => b.createdAt.localeCompare(a.createdAt)))
const currentHistoryName = computed(() => analysisHistory.value.find(entry => entry.id === existingJobId.value)?.name ?? '')

function rememberAnalysis(id: string, status: HistoryStatus, name = '') {
  const previous = analysisHistory.value.find(entry => entry.id === id)
  const entry: HistoryEntry = { id, name: name || previous?.name || savedMediaName(id) || '历史分析',
    addedAt: previous?.addedAt ?? new Date().toISOString(), status }
  analysisHistory.value = [entry, ...analysisHistory.value.filter(item => item.id !== id)]
  localStorage.setItem('analysisHistory:v1', JSON.stringify(analysisHistory.value))
}

function historyStatusLabel(status: HistoryStatus) {
  return { unknown: '未查询', queued: '排队中', processing: '分析中', completed: '已完成', failed: '失败' }[status]
}

function clearLoadedAnalysis() {
  analysisState.value = ''
  analysisProgress.value = null
  clearSubtitleJob()
  sourceLanguage.value = 'und'
  transcript.value = []
  visualEvidence.value = []
  pageGroups.value = []
  mindMap.value = null
  selectedMindNode.value = null
  activeSegmentId.value = ''
  review.value = null
  failedJobId.value = ''
  videoChapters.value = []
  chapterStatus.value = 'not_requested'
  chapterController?.abort()
}
function invalidateAnalysisRequests() {
  analysisRequests.invalidate()
  mindMapRequests.invalidate()
  isAnalysisPending.value = false
  generatingMindMap.value = false
}
function detachPlayback() {
  video.value?.pause()
  selectedFile.value = null
  selectedFingerprint.value = ''
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  videoUrl.value = ''
  video.value = null
  filename.value = ''
  currentPlaybackMs.value = 0
}
async function chooseVideo(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''
  const request = selectionRequests.begin()
  const previousId = existingJobId.value
  const expected = localStorage.getItem(`analysisMedia:${previousId}`)
  const previous = { segments: transcript.value, language: sourceLanguage.value, frames: visualEvidence.value,
    pages: pageGroups.value, map: mindMap.value, review: review.value }
  invalidateAnalysisRequests()
  setAnalysisId('')
  clearLoadedAnalysis()
  detachPlayback()
  checkingMedia.value = true
  error.value = ''
  status.value = '正在核对本地媒体文件…'
  try {
    const fingerprint = await mediaFingerprint(file)
    if (!request.current()) return
    const binding = mediaBindingState(expected, file.size, fingerprint)
    selectedFile.value = file
    selectedFingerprint.value = fingerprint
    videoUrl.value = URL.createObjectURL(file)
    filename.value = file.name
    checkingMedia.value = false
    if (previousId && binding === 'matched') {
      setAnalysisId(previousId)
      localStorage.setItem('lastAnalysisId', previousId)
      transcript.value = previous.segments
      sourceLanguage.value = previous.language
      visualEvidence.value = previous.frames
      pageGroups.value = previous.pages
      mindMap.value = previous.map
      review.value = previous.review
      readSubtitleJob(previousId)
      status.value = '视频指纹匹配；已关联该任务，可回放课程依据'
    } else {
      localStorage.removeItem('lastAnalysisId')
      status.value = previousId ? binding === 'unverified'
        ? '旧记录缺少有效指纹，无法确认关联；当前视频可重新分析，历史资料仍可查看'
        : '视频指纹不匹配，已解除旧关联；当前视频可开始分析'
        : '本地视频已就绪；可上传进行分析'
    }
  } catch {
    if (request.current()) error.value = '无法读取本地文件，请重新选择'
  } finally {
    if (request.current()) checkingMedia.value = false
  }
}

async function waitForAnalysis(id: string, request: RequestTicket) {
    for (let attempt = 0; attempt < 1800; attempt++) {
      if (!request.current() || existingJobId.value !== id) return
      await new Promise(resolve => setTimeout(resolve, 1000))
      if (!request.current() || existingJobId.value !== id) return
      const query = await fetch(`${apiBase}/transcriptions/${id}`, { signal: request.signal })
      if (!query.ok) throw new Error(`查询转写状态失败：HTTP ${query.status}`)
      const job: TranscriptionJob = await query.json()
      if (!request.current() || existingJobId.value !== id) return
      if (['queued', 'processing', 'completed', 'failed'].includes(job.status) &&
          analysisHistory.value.find(entry => entry.id === id)?.status !== job.status) {
        rememberAnalysis(id, job.status as HistoryStatus)
      }
      analysisState.value = job.status
      analysisProgress.value = job.progress ?? null
      status.value = job.status === 'queued' ? '等待分析任务…' : '正在分析…'
      if (job.status === 'failed') {
        failedJobId.value = id
        throw new Error(job.error || '分析失败')
      }
      if (job.status === 'completed') {
        unavailableFrames.value = new Set()
        transcript.value = job.result?.segments ?? []
        sourceLanguage.value = job.result?.language || 'und'
        visualEvidence.value = job.result?.visualEvidence ?? []
        pageGroups.value = job.result?.pageGroups ?? []
        mindMap.value = job.result?.mindMap ?? null
        selectedMindNode.value = null
        activeSegmentId.value = ''
        review.value = job.result?.review ?? null
        failedJobId.value = ''
        const pageStatuses = pageGroups.value.map(page =>
          (job.result?.visualAnalysisMode === 'ocr_only' ? page.textAnalysis : page.imageAnalysis)?.status)
        const completedCount = pageStatuses.filter(value => value === 'completed').length
        const inferredCount = pageStatuses.filter(value => value === 'inferred').length
        const unverifiedCount = pageStatuses.filter(value => value === 'unverified').length
        const routeName = job.result?.visualAnalysisMode === 'ocr_only' ? '语音＋OCR 文字理解' : '语音＋图片理解'
        status.value = `分析完成：转写 ${transcript.value.length} 段；候选画面 ${visualEvidence.value.length} 张、归为 ${pageGroups.value.length} 页；OCR ${job.result?.ocrModelId || '未记录'}；${routeName}确认 ${completedCount} 页、含推导 ${inferredCount} 页、待核实 ${unverifiedCount} 页；导图${mindMap.value?.status === 'completed' ? '已生成' : mindMap.value?.status === 'failed' ? '部分失败' : '暂无'}`
        if (selectedFile.value && !confirmedMedia.value) {
          const binding = mediaBindingState(localStorage.getItem(`analysisMedia:${id}`), selectedFile.value.size, selectedFingerprint.value)
          detachPlayback()
          status.value += binding === 'unverified'
            ? '；记录缺少有效指纹，历史资料可查看，但无法关联当前视频回放'
            : '；当前视频指纹不匹配，请重新选择原视频'
        }
        return
      }
    }
    throw new Error('等待分析超时')
}

async function runTranscription() {
  if (!selectedFile.value || isAnalysisPending.value || checkingMedia.value) return
  const request = analysisRequests.begin()
  const file = selectedFile.value
  const fingerprint = selectedFingerprint.value
  if (file.size > 2 * 1024 * 1024 * 1024) {
    error.value = '当前最多上传 2 GB'
    return
  }
  isAnalysisPending.value = true
  error.value = ''
  clearSubtitleJob()
  transcript.value = []
  visualEvidence.value = []
  pageGroups.value = []
  mindMap.value = null
  selectedMindNode.value = null
  activeSegmentId.value = ''
  review.value = null
  failedJobId.value = ''
  setAnalysisId('')
  analysisState.value = 'uploading'
  analysisProgress.value = null
  status.value = '正在临时上传视频…'
  try {
    const form = new FormData()
    form.append('file', file)
    form.append('visualAnalysisMode', visualAnalysisMode.value)
    form.append('coarseChangePercent', coarseChangePercent.value)
    form.append('coarseSampleSeconds', String(coarseSampleSeconds.value))
    if (analysisRegion.value||ignoredRegion.value) form.append('ignoredRegion',JSON.stringify(analysisRegion.value?{analysisRegion:analysisRegion.value,ignoredRegion:ignoredRegion.value}:ignoredRegion.value))
    form.append('aiSubtitles', 'false')
    form.append('subtitleTargetLanguage', subtitleTargetLanguage.value)
    const response = await fetch(`${apiBase}/transcriptions`, { method: 'POST', body: form, signal: request.signal })
    if (!response.ok) throw new Error(`上传失败：HTTP ${response.status}`)
    const created: TranscriptionJob = await response.json()
    if (!request.current()) return
    localStorage.setItem(`analysisMedia:${created.id}`, JSON.stringify({ name: file.name, size: file.size, fingerprint }))
    setAnalysisId(created.id)
    localStorage.setItem('lastAnalysisId', created.id)
    rememberAnalysis(created.id, 'queued', file.name)
    readSubtitleJob(created.id)
    analysisState.value = created.status
    await waitForAnalysis(created.id, request)
  } catch (cause) {
    if (!request.current()) return
    error.value = cause instanceof Error ? cause.message : String(cause)
    if (analysisState.value !== 'failed') analysisState.value = 'interrupted'
    status.value = '分析未完成'
  } finally {
    if (request.current()) isAnalysisPending.value = false
  }
}

async function loadExistingAnalysis() {
  if (isAnalysisPending.value) return
  const id = existingJobId.value.trim()
  if (!jobIdPattern.test(id)) {
    error.value = '请输入有效的分析编号'
    return
  }
  const request = analysisRequests.begin()
  isAnalysisPending.value = true
  if (!analysisHistory.value.some(entry => entry.id === id)) rememberAnalysis(id, 'unknown')
  error.value = ''
  status.value = '正在读取已保存的分析结果…'
  clearLoadedAnalysis()
  analysisState.value = 'reading'
  let playbackWarning = ''
  if (selectedFile.value && !confirmedMedia.value) {
    playbackWarning = mediaBindingState(localStorage.getItem(`analysisMedia:${id}`), selectedFile.value.size, selectedFingerprint.value) === 'unverified'
      ? '；记录缺少有效指纹，无法确认当前视频，历史资料仍可查看'
      : '；视频指纹不匹配，已解除当前视频关联'
    detachPlayback()
  }
  readSubtitleJob(id)
  try {
    await waitForAnalysis(id, request)
    if (request.current() && existingJobId.value === id) {
      localStorage.setItem('lastAnalysisId', id)
      status.value += playbackWarning
    }
  } catch (cause) {
    if (!request.current()) return
    error.value = cause instanceof Error ? cause.message : String(cause)
    if (analysisState.value !== 'failed') analysisState.value = 'interrupted'
    status.value = '未能读取分析结果'
  } finally {
    if (request.current()) isAnalysisPending.value = false
  }
}

async function openHistory(entry: HistoryEntry) {
  if (isAnalysisPending.value) return
  if (existingJobId.value !== entry.id) {
    clearSubtitleJob()
    transcript.value = []
    visualEvidence.value = []
    pageGroups.value = []
    mindMap.value = null
    selectedMindNode.value = null
    activeSegmentId.value = ''
    if (selectedFile.value && mediaBindingState(localStorage.getItem(`analysisMedia:${entry.id}`), selectedFile.value.size, selectedFingerprint.value) !== 'matched') detachPlayback()
  }
  setAnalysisId(entry.id)
  rightTab.value = 'map'
  await loadExistingAnalysis()
}

async function deleteHistory(entry: HistoryEntry) {
  if (isAnalysisPending.value || deletingHistoryId.value) return
  if (!window.confirm(`永久删除“${entry.name}”的分析结果、服务器截图、练习及答题记录和本机笔记？此操作无法撤销。电脑上的原视频不会删除。`)) return
  const deletingCurrentSubtitles = subtitleCourseId.value === entry.id
  if (deletingCurrentSubtitles) clearSubtitleJob()
  deletingHistoryId.value = entry.id
  historyError.value = ''
  try {
    const response = await fetch(`${apiBase}/transcriptions/${entry.id}`, { method: 'DELETE' })
    if (response.status === 409) throw new Error('这条任务还在排队或分析中，请完成后再删除。')
    if (response.status !== 204 && response.status !== 404) throw new Error(`删除失败：HTTP ${response.status}`)
    analysisHistory.value = analysisHistory.value.filter(item => item.id !== entry.id)
    localStorage.setItem('analysisHistory:v1', JSON.stringify(analysisHistory.value))
    localStorage.removeItem(`analysisMedia:${entry.id}`)
    if (localStorage.getItem('lastAnalysisId') === entry.id) localStorage.removeItem('lastAnalysisId')
    studyNotes.value = studyNotes.value.filter(note => note.scope !== entry.id)
    localStorage.setItem('studyNotes:v1', JSON.stringify(studyNotes.value))
    if (existingJobId.value === entry.id) {
      analysisState.value = ''
      analysisProgress.value = null
      clearSubtitleJob()
      invalidateAnalysisRequests()
      setAnalysisId('')
      transcript.value = []
      visualEvidence.value = []
      pageGroups.value = []
      mindMap.value = null
      selectedMindNode.value = null
      activeSegmentId.value = ''
      review.value = null
      failedJobId.value = ''
      unavailableFrames.value = new Set()
      status.value = '这条分析记录已删除；电脑上的原视频仍可播放或重新分析。'
    }
  } catch (cause) {
    historyError.value = cause instanceof Error ? cause.message : String(cause)
    if (deletingCurrentSubtitles && existingJobId.value === entry.id) readSubtitleJob(entry.id)
  } finally {
    deletingHistoryId.value = ''
  }
}

async function retryAnalysis() {
  if (!failedJobId.value || isAnalysisPending.value) return
  const request = analysisRequests.begin()
  isAnalysisPending.value = true
  error.value = ''
  analysisState.value = 'queued'
  analysisProgress.value = null
  status.value = '正在重新分析保留的上传文件…'
  try {
    const id = failedJobId.value
    const response = await fetch(`${apiBase}/transcriptions/${id}/retry`, { method: 'POST', signal: request.signal })
    if (!response.ok) throw new Error(`重试失败：HTTP ${response.status}`)
    if (!request.current()) return
    readSubtitleJob(id)
    await waitForAnalysis(id, request)
  } catch (cause) {
    if (!request.current()) return
    error.value = cause instanceof Error ? cause.message : String(cause)
    if (analysisState.value !== 'failed') analysisState.value = 'interrupted'
    status.value = '分析未完成'
  } finally {
    if (request.current()) isAnalysisPending.value = false
  }
}

async function generateExistingMindMap(refresh = false) {
  if (!existingJobId.value || generatingMindMap.value) return
  const id = existingJobId.value
  const request = mindMapRequests.begin()
  generatingMindMap.value = true
  error.value = ''
  status.value = '正在从已保存的转写生成可回溯导图…'
  try {
    const response = await fetch(`${apiBase}/transcriptions/${id}/mind-map${refresh ? '?refresh=true' : ''}`, { method: 'POST', signal: request.signal })
    if (!response.ok) throw new Error(`导图生成失败：HTTP ${response.status}`)
    const result = await response.json() as MindMapResult
    if (!request.current() || existingJobId.value !== id) return
    mindMap.value = result
    selectedMindNode.value = null
    activeSegmentId.value = ''
    status.value = mindMap.value.status === 'completed' ? '导图已生成并保存；点击节点可回放原片段'
      : '导图未完全生成；有依据的节点仍可回放，也可以重试'
  } catch (cause) {
    if (!request.current() || existingJobId.value !== id) return
    error.value = cause instanceof Error ? cause.message : String(cause)
    status.value = '导图生成未完成；原转写和页面分析仍可查看'
  } finally {
    if (request.current()) generatingMindMap.value = false
  }
}

function seekTo(startMs: number, sourceId?: string) {
  if (sourceId) activeSegmentId.value = sourceId
  currentPlaybackMs.value = startMs
  if (!video.value || checkingMedia.value || ((existingJobId.value || sourceId) && !confirmedMedia.value)) {
    status.value = '课程依据可查看；请先选择指纹匹配的原视频或录音，再回放这一段'
    return
  }
  video.value.currentTime = startMs / 1000
  void video.value.play().catch(() => { status.value = '已跳转，请点击播放器继续播放' })
}

function selectExpandedMindNode(node: MindNode) {
  expandedMap.value = false
  void selectMindMapNode(node)
}

async function selectMindMapNode(node: MindNode) {
  const id = existingJobId.value
  const fingerprint = selectedFingerprint.value
  selectedMindNode.value = node
  activeSegmentId.value = node.evidenceRefs[0]?.sourceId ?? ''
  currentPlaybackMs.value = node.evidenceRefs[0]?.startMs ?? currentPlaybackMs.value
  await nextTick()
  if (id !== existingJobId.value || fingerprint !== selectedFingerprint.value) return
  scrollTranscriptTo(activeSegmentId.value)
  const result = await jumpToMindMapNode(node, confirmedMedia.value ? video.value : null)
  if (id !== existingJobId.value || fingerprint !== selectedFingerprint.value) return
  if (result === 'missing_media') status.value = '导图依据已显示；请重新选择指纹匹配的本地原视频或录音以回放'
  else if (result === 'paused') status.value = '已跳到对应位置，请点击播放器继续播放'
  else if (result === 'no_evidence') status.value = '这个节点没有可回放的课程依据'
  else video.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function scrollTranscriptTo(sourceId: string) {
  const target = document.getElementById(`transcript-${sourceId}`)
  if (target && transcriptList.value) {
    const listBox = transcriptList.value.getBoundingClientRect()
    const rowBox = target.getBoundingClientRect()
    transcriptList.value.scrollTop += rowBox.top - listBox.top - listBox.height / 3
  }
  const sidebarTarget = document.getElementById(`sidebar-transcript-${sourceId}`)
  if (sidebarTarget && sidebarTranscriptList.value) {
    const listBox = sidebarTranscriptList.value.getBoundingClientRect()
    const rowBox = sidebarTarget.getBoundingClientRect()
    sidebarTranscriptList.value.scrollTop += rowBox.top - listBox.top - listBox.height / 3
  }
}

function saveNote() {
  const text = noteDraft.value.trim()
  const scope = transcript.value.length && existingJobId.value ? existingJobId.value : noteScopes.value[0]
  if (!text || !scope) return
  studyNotes.value = [{ id: crypto.randomUUID(), scope, timeMs: currentPlaybackMs.value,
    text, createdAt: new Date().toISOString() }, ...studyNotes.value]
  localStorage.setItem('studyNotes:v1', JSON.stringify(studyNotes.value))
  noteDraft.value = ''
}

function deleteNote(id: string) {
  studyNotes.value = studyNotes.value.filter(note => note.id !== id)
  localStorage.setItem('studyNotes:v1', JSON.stringify(studyNotes.value))
}

function handleSidebarTabKeydown(event: KeyboardEvent) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  const current = rightTabOrder.indexOf(rightTab.value)
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? rightTabOrder.length - 1
    : (current + (event.key === 'ArrowRight' ? 1 : -1) + rightTabOrder.length) % rightTabOrder.length
  rightTab.value = rightTabOrder[next]
  ;(event.currentTarget as HTMLElement).querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus()
}

function formatTime(timeMs: number) { return new Date(timeMs).toISOString().slice(11, 19) }
function formatHistoryDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
function frameAt(timeMs: number) { return visualEvidence.value.find(frame => frame.frameTimeMs === timeMs) }
function markFrameUnavailable(timeMs: number) { unavailableFrames.value = new Set([...unavailableFrames.value, timeMs]) }
function syncPlayback(event: Event) {
  const timeMs = (event.target as HTMLVideoElement).currentTime * 1000
  currentPlaybackMs.value = timeMs
  let low = 0
  let high = transcript.value.length - 1
  let nearest = -1
  while (low <= high) {
    const mid = (low + high) >> 1
    if (transcript.value[mid].startMs <= timeMs) { nearest = mid; low = mid + 1 }
    else high = mid - 1
  }
  const sourceId = nearest >= 0 ? transcript.value[nearest].id : ''
  if (sourceId && sourceId !== activeSegmentId.value) {
    activeSegmentId.value = sourceId
    void nextTick().then(() => scrollTranscriptTo(sourceId))
  }
}

onUnmounted(() => {
  selectionRequests.invalidate()
  analysisRequests.invalidate()
  mindMapRequests.invalidate()
  clearCompatibility()
  cueStyleElement.remove()
  clearSubtitleJob()
  video.value?.textTracks.removeEventListener('change', refreshSubtitleToggle)
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  if (subtitleUrl.value) URL.revokeObjectURL(subtitleUrl.value)
})
</script>

<template>
  <main class="study-app">
    <header class="app-header">
      <div class="brand"><span class="brand-symbol"><StudyIcon name="play" /></span><span class="brand-video">Video</span><span>Study</span></div>
      <div class="header-context"><strong>沉浸式学习台</strong><span class="header-divider" aria-hidden="true"></span><span class="header-file">{{ filename || currentHistoryName || '选择一段课程视频，开始建立知识导图' }}</span></div>
      <div class="header-actions">
        <span v-if="mindMap?.status === 'completed'" class="ready-indicator">已生成 {{ mindMap.root.children.length }} 个主题</span>
        <label class="file-picker"><StudyIcon name="upload" />选择本地视频 <input type="file" accept="video/*,audio/*" @change="chooseVideo" /></label>
        <button v-if="selectedFile && !transcript.length" class="run" type="button" :disabled="isAnalysisPending" @click="runTranscription">{{ isAnalysisPending ? '处理中…' : '开始分析' }}</button>
      </div>
      <AnalysisProgressBar :state="analysisState" :progress="analysisProgress" />
    </header>
    <aside class="study-sidebar" aria-label="学习工具">
      <div class="sidebar-heading"><div><span class="eyebrow">YOUR STUDY SPACE</span><h2>学习工作台</h2></div><span class="workspace-mark"><StudyIcon name="spark" />跟着课程，找到依据</span></div>
      <div class="sidebar-tabs" :style="{ '--tab-index': rightTabOrder.indexOf(rightTab) }" role="tablist" aria-label="学习工具视图" @keydown="handleSidebarTabKeydown">
        <button type="button" role="tab" aria-controls="tab-map" :aria-selected="rightTab === 'map'" :class="{ active: rightTab === 'map' }" @click="rightTab = 'map'"><StudyIcon name="map" />思维导图</button>
        <button type="button" role="tab" aria-controls="tab-practice" :aria-selected="rightTab === 'practice'" :class="{ active: rightTab === 'practice' }" @click="rightTab = 'practice'"><StudyIcon name="practice" />AI 练习</button>
        <button type="button" role="tab" aria-controls="tab-transcript" :aria-selected="rightTab === 'transcript'" :class="{ active: rightTab === 'transcript' }" @click="rightTab = 'transcript'"><StudyIcon name="transcript" />字幕原文</button>
        <button type="button" role="tab" aria-controls="tab-slides" :aria-selected="rightTab === 'slides'" :class="{ active: rightTab === 'slides' }" @click="rightTab = 'slides'"><StudyIcon name="slides" />课件画面</button>
        <button type="button" role="tab" aria-controls="tab-notes" :aria-selected="rightTab === 'notes'" :class="{ active: rightTab === 'notes' }" @click="rightTab = 'notes'"><StudyIcon name="notes" />随手笔记</button>
        <button type="button" role="tab" aria-controls="tab-history" :aria-selected="rightTab === 'history'" :class="{ active: rightTab === 'history' }" @click="rightTab = 'history'"><StudyIcon name="history" />历史记录</button>
      </div>
      <section v-show="rightTab === 'map'" id="tab-map" class="sidebar-pane" role="tabpanel" aria-label="思维导图">
        <div v-if="mindMap" class="mind-map-panel">
          <div class="mind-map-heading"><div><span class="eyebrow">KNOWLEDGE MAP</span><h2>知识导图</h2><p>核心知识看导图，例题按时间回看</p></div>
            <div class="mind-map-heading-actions"><button v-if="mindMap.root.children.length" type="button" class="expand-map-button" @click="expandedMap = true">放大查看</button><span class="mind-map-badge">{{ mindMap.root.children.length }} 个主题</span></div></div>
          <p v-if="mindMap.status === 'empty'" class="status">{{ mindMap.examples?.length ? '本段课程未提取到核心知识，可通过下方例题节点回看。' : '没有可用的核心知识依据，暂时无法生成导图。' }}</p>
          <p v-else-if="mindMap.status === 'failed'" class="status">{{ mindMap.root.children.length ? '部分导图内容未生成；已显示的节点仍可查看原文和回放。' : '导图尚未生成；原转写和页面分析仍可查看，可以重试。' }}</p>
          <div v-if="selectedMindNode?.evidenceRefs.length" class="mind-source">
            <strong>{{ selectedMindNode.title }} · 课程依据</strong>
            <button v-for="source in selectedMindNode.evidenceRefs" :key="source.sourceId" type="button" class="mind-source-link" @click="seekTo(source.startMs, source.sourceId)">
              <span class="time">{{ formatTime(source.startMs) }}</span> {{ source.quote }}
            </button>
          </div>
          <MindMapCanvas v-if="mindMap.root.children.length" :root="mindMap.root" @select="selectMindMapNode" />
          <section v-if="mindMap.examples?.length" class="example-timeline" aria-label="例题时间节点">
            <div class="example-timeline-heading"><h3>例题时间节点</h3><span>{{ mindMap.examples.length }} 个讲解片段</span></div>
            <p>例题独立列出，点击回看对应讲解。</p>
            <button v-for="example in mindMap.examples" :key="example.id" type="button" @click="seekTo(example.evidenceRefs[0]?.startMs ?? example.startMs, example.evidenceRefs[0]?.sourceId)"><span class="time">{{ formatTime(example.startMs) }}</span><span>{{ example.title }}</span><StudyIcon name="play" /></button>
          </section>
        </div>
        <div v-else class="sidebar-empty">
          <div class="map-preview" aria-hidden="true"><span class="preview-root"><StudyIcon name="play" />课程</span><i></i><div><span><StudyIcon name="map" />知识脉络</span><span><StudyIcon name="transcript" />原文依据</span><span><StudyIcon name="notes" />学习笔记</span></div></div>
          <span class="eyebrow">KNOWLEDGE MAP</span><h3>让知识点回到原视频</h3>
          <p>分析完成后，这里会生成可展开的课程导图。点击任一节点，就能回看老师讲解它的片段和原句。</p>
          <div class="empty-steps"><span><b>01</b> 选择本地课程视频</span><span><b>02</b> 运行语音与画面分析</span><span><b>03</b> 点击导图回看依据</span></div>
          <p class="empty-hint" :class="{ 'is-processing': isAnalysisPending }"><span v-if="isAnalysisPending" class="activity-spinner" aria-hidden="true"></span>{{ isAnalysisPending ? '正在分析课程，完成后导图将在这里显示。你可以继续观看本地视频。' : selectedFile ? '视频已选好，点击顶部“开始分析”；已有任务可在下方按编号读取结果。' : '先点击右上角“选择本地视频”；已有任务可在下方按编号读取结果。' }}</p>
        </div>
      </section>
      <section v-show="rightTab === 'practice'" id="tab-practice" class="sidebar-pane" role="tabpanel" aria-label="AI 练习"><AiPractice :course-id="(transcript.length || pageGroups.length || mindMap) && existingJobId ? existingJobId : undefined" :has-media="!!selectedFile || checkingMedia" :playback-ready="confirmedMedia" :mind-map="mindMap" :selected-node-id="selectedMindNode?.id" :ready="!!transcript.length" @seek="seekTo" /></section>
      <section v-show="rightTab === 'transcript'" id="tab-transcript" class="sidebar-pane" role="tabpanel" aria-label="字幕原文">
        <div class="sidebar-pane-heading"><div><span class="eyebrow">TRANSCRIPT</span><h3>字幕原文</h3></div><span>{{ transcript.length }} 段</span></div>
        <template v-if="transcript.length">
          <label class="sidebar-search-label" for="transcript-search">搜索课程内容</label>
          <input id="transcript-search" v-model="transcriptQuery" class="sidebar-search" type="search" placeholder="输入关键词查找讲解…" />
          <p v-if="subtitleChanges.length" class="subtitle-review-hint">原文保留如下；展开标记可查看 AI {{ subtitleIsTranslation ? '翻译' : '校正' }}和依据。</p>
          <div ref="sidebarTranscriptList" class="sidebar-transcript-list">
            <div v-for="segment in filteredTranscript" :key="segment.id" class="transcript-entry">
              <button :id="`sidebar-transcript-${segment.id}`" type="button" class="sidebar-row" :class="{ 'active-segment': segment.id === activeSegmentId }" @click="seekTo(segment.startMs, segment.id)">
                <span class="time">{{ formatTime(segment.startMs) }}</span><span>{{ segment.text }}</span>
              </button>
              <details v-if="subtitleChangeById.has(segment.id)" class="subtitle-change">
                <summary>查看 AI {{ subtitleIsTranslation ? '翻译' : '校正' }}</summary>
                <p><strong>原文</strong>{{ subtitleChangeById.get(segment.id)?.originalText }}</p>
                <p><strong>AI {{ subtitleIsTranslation ? '翻译' : '校正' }}</strong>{{ subtitleChangeById.get(segment.id)?.text }}</p>
                <p>{{ subtitleChangeById.get(segment.id)?.reason }}</p>
                <div v-if="subtitleChangeById.get(segment.id)?.evidence?.length" class="subtitle-change-evidence">
                  <span>相关课件文字</span>
                  <button v-for="(evidence, index) in subtitleChangeById.get(segment.id)?.evidence" :key="index" type="button" @click="seekTo(evidence.sourceFrameTimeMs)">{{ formatTime(evidence.sourceFrameTimeMs) }} · {{ evidence.text }}</button>
                </div>
              </details>
            </div>
            <p v-if="!filteredTranscript.length" class="sidebar-message">没有找到包含“{{ transcriptQuery }}”的讲解。</p>
          </div>
        </template>
        <div v-else class="sidebar-empty compact"><h3>字幕还没生成</h3><p>分析课程后，可在这里搜索老师说过的话，点击任一行直接回放。</p></div>
      </section>
      <section v-show="rightTab === 'slides'" id="tab-slides" class="sidebar-pane" role="tabpanel" aria-label="课件画面">
        <div class="sidebar-pane-heading"><div><span class="eyebrow">VISUAL EVIDENCE</span><h3>课件画面</h3></div><span>{{ pageGroups.length ? `${pageGroups.length} 页` : `${visualEvidence.length} 张候选图` }}</span></div>
        <PageGallery v-if="pageGroups.length" :pages="pageGroups" :course-id="existingJobId" :time-ms="currentPlaybackMs" @seek="seekTo" />
        <template v-else-if="visualEvidence.length">
          <p class="sidebar-message">这是旧任务的候选截图记录；原图可能已被清理，文字和时间仍可查看。</p>
          <div class="sidebar-slide-list"><button v-for="frame in visualEvidence" :key="frame.frameTimeMs" type="button" class="sidebar-slide-row" @click="seekTo(frame.frameTimeMs)"><span class="time">{{ formatTime(frame.frameTimeMs) }}</span><span>{{ frame.imageAnalysis?.title || frame.ocrBlocks.slice(0, 2).map(block => block.text).join(' · ') || '候选画面' }}</span></button></div>
        </template>
        <div v-else class="sidebar-empty compact"><h3>课件证据还没生成</h3><p>分析时会抽取关键画面、识别课件文字，并关联到视频时间。</p></div>
      </section>
      <section v-show="rightTab === 'notes'" id="tab-notes" class="sidebar-pane" role="tabpanel" aria-label="随手笔记">
        <div class="sidebar-pane-heading"><div><span class="eyebrow">MY NOTES</span><h3>随手笔记</h3></div><span>{{ visibleNotes.length }} 条</span></div>
        <div class="note-editor"><p>记录当前播放位置 <strong>{{ formatTime(currentPlaybackMs) }}</strong></p><textarea v-model="noteDraft" rows="4" maxlength="2000" placeholder="记下自己的理解、疑问或需要回看的地方…"></textarea><div><span>仅保存在当前设备</span><button type="button" class="run" :disabled="!noteDraft.trim() || !noteScopes.length" @click="saveNote">保存笔记</button></div></div>
        <p v-if="!noteScopes.length" class="sidebar-message">选择视频或读取分析结果后即可记笔记。</p>
        <div v-if="visibleNotes.length" class="sidebar-note-list"><article v-for="note in visibleNotes" :key="note.id" class="note-item"><div><button type="button" class="text-link time" @click="seekTo(note.timeMs)">{{ formatTime(note.timeMs) }} · 回放</button><button type="button" class="note-delete" :aria-label="`删除 ${formatTime(note.timeMs)} 的笔记`" @click="deleteNote(note.id)">删除</button></div><p>{{ note.text }}</p></article></div>
        <p v-else-if="noteScopes.length" class="sidebar-message">还没有笔记。播放到想记住的地方，写下内容并保存。</p>
      </section>
      <section v-show="rightTab === 'history'" id="tab-history" class="sidebar-pane" role="tabpanel" aria-label="历史记录">
        <div class="sidebar-pane-heading"><div><span class="eyebrow">MY LIBRARY</span><h3>本机历史</h3></div><span>{{ analysisHistory.length }} 条记录</span></div>
        <p class="sidebar-message">保存的是任务编号和课程记录，不保存视频。点击记录可读取字幕、导图和课件文字；回放时请重新选择本地原视频。</p>
        <p v-if="historyError" class="history-error" role="alert">{{ historyError }}</p>
        <div v-if="analysisHistory.length" class="history-list">
          <article v-for="entry in analysisHistory" :key="entry.id" class="history-item">
            <button type="button" class="history-open" :disabled="isAnalysisPending || !!deletingHistoryId" @click="openHistory(entry)">
              <span class="history-item-top"><strong>{{ entry.name }}</strong><span>上次状态：{{ historyStatusLabel(entry.status) }}</span></span>
              <small>加入本机 {{ formatHistoryDate(entry.addedAt) }} · {{ entry.id }}</small>
            </button>
            <button type="button" class="history-delete" :aria-label="`永久删除 ${entry.name} 的分析记录`" :disabled="isAnalysisPending || !!deletingHistoryId" @click="deleteHistory(entry)">{{ deletingHistoryId === entry.id ? '删除中…' : '删除' }}</button>
          </article>
        </div>
        <div v-else class="sidebar-empty compact"><h3>还没有历史记录</h3><p>第一次分析或按编号读取结果后，记录会出现在这里。</p></div>
        <p class="sidebar-message">此列表只保存在当前设备。清除浏览器数据会清空列表，但不会自动删除服务器上的分析结果。</p>
      </section>
    </aside>
    <section class="workspace">
      <div class="panel player-panel">
        <div class="section-title"><h2>课程视频</h2><div class="player-tools"><button type="button" class="subtitle-toggle workspace-entry" @click="openVideoWorkspace"><StudyIcon name="slides" />视频工作台<span v-if="ignoredRegion||analysisRegion" class="workspace-entry-dot" aria-label="已保存画面区域"></span></button><button v-if="selectedFile" type="button" class="subtitle-toggle" :disabled="compatibilityBusy" title="使用后台显卡生成 H.264 播放副本，需要上传原视频，不重新分析课程" @click="generateCompatibility">{{ compatibilityBusy ? '转换中…' : compatibilityActive ? '返回原视频' : compatibilityId ? '使用兼容副本' : '显卡兼容播放' }}</button><button v-if="compatibilityBusy" type="button" class="subtitle-toggle" @click="clearCompatibility">取消转码</button><button v-if="transcript.length && videoUrl" type="button" class="subtitle-toggle" :aria-pressed="subtitleEnabled" @click="subtitleEnabled = !subtitleEnabled"><StudyIcon name="transcript" />字幕{{ subtitleEnabled ? '已开启' : '已关闭' }}</button><span>{{ compatibilityActive ? '兼容播放' : '本地播放' }} · {{ videoUrl ? formatTime(currentPlaybackMs) : '尚未选择文件' }}</span></div></div>
        <p v-if="compatibilityMessage" class="empty-hint" role="status" aria-live="polite">{{ compatibilityMessage }}</p>
        <div v-if="transcript.length" class="subtitle-controls">
          <SubtitleSettings v-model="subtitleAppearance" />
          <div class="subtitle-mode" role="group" aria-label="字幕版本">
            <button type="button" :aria-pressed="selectedSubtitles.mode === 'original'" @click="subtitleMode = 'original'">原文字幕</button>
            <button type="button" :aria-pressed="selectedSubtitles.mode === 'ai'" :disabled="!aiSubtitlesAvailable" @click="subtitleMode = 'ai'">AI {{ subtitleIsTranslation ? '翻译' : '校正' }}字幕</button>
          </div>
          <label v-if="subtitleCourseId" class="subtitle-target" for="player-subtitle-language">AI 字幕语言
            <select id="player-subtitle-language" v-model="subtitleTargetLanguage" :disabled="requestingSubtitles || isAnalysisPending"><option value="source">保持原语言（仅校正）</option><option value="zh">中文</option><option value="en">English</option></select>
          </label>
          <button v-if="subtitleCourseId" type="button" class="subtitle-generate" :disabled="!canGenerateSubtitles" @click="generateSubtitles">{{ requestingSubtitles || ['awaiting_source', 'queued', 'processing'].includes(subtitleJob?.status ?? '') ? '生成中…' : subtitleNeedsUpdate ? '更新 AI 字幕' : ['completed', 'partial'].includes(subtitleJob?.status ?? '') ? '重新生成 AI 字幕' : subtitleJob?.status === 'failed' ? '重试生成 AI 字幕' : '生成 AI 字幕' }}</button>
        </div>
        <p v-if="subtitleStatusMessage" class="subtitle-status" :class="{ 'subtitle-status-warning': subtitleRequestError || ['failed', 'partial', 'unsupported'].includes(subtitleJob?.status ?? '') }" role="status" aria-atomic="true">{{ subtitleStatusMessage }}</p>
        <ChapterPlayer v-if="videoUrl" :src="videoUrl" :chapters="confirmedMedia ? videoChapters : []" :chapter-status="confirmedMedia ? chapterStatus : 'not_requested'" @ready="video = $event" @timeupdate="syncPlayback"><track v-if="subtitleUrl && confirmedMedia" :key="subtitleUrl" :src="subtitleUrl" kind="subtitles" :label="selectedSubtitles.mode === 'ai' ? 'AI 字幕' : '原文字幕'" :srclang="selectedSubtitles.language" default @load="syncSubtitleVisibility" /></ChapterPlayer>
        <div v-else class="empty-player">
          <div class="player-orbit orbit-one" aria-hidden="true"></div><div class="player-orbit orbit-two" aria-hidden="true"></div>
          <div class="player-welcome"><span class="player-play-mark"><StudyIcon name="play" /></span><span class="player-kicker">WATCH. UNDERSTAND. CONNECT.</span><h3>从一节课，连接每个知识点</h3><p>选择本地视频或录音，开启你的学习工作台</p><label class="player-file-picker"><StudyIcon name="upload" />选择课程文件<input type="file" accept="video/*,audio/*" @change="chooseVideo" /></label></div>
          <span class="player-local-badge"><StudyIcon name="lock" />本地播放 · 原文件保留在你的电脑</span>
        </div>
        <p class="player-caption"><StudyIcon name="lock" />{{ filename || '本地回放 · 分析后点击知识节点，回到老师的讲解现场' }}</p>
      </div>
      <details class="panel video-overview">
        <summary><span class="video-overview-title"><StudyIcon name="spark" />AI 解读</span><span class="video-overview-hint">课程整体分析</span><span class="video-overview-chevron" aria-hidden="true">⌄</span></summary>
        <AiOverview :course-id="existingJobId" :ready="!!transcript.length" />
      </details>
      <div class="panel results-panel">
        <div class="section-title"><h2>课程依据</h2><span>{{ transcript.length }} 段字幕 · {{ pageGroups.length ? `${pageGroups.length} 页课件` : `${visualEvidence.length} 张候选画面` }}</span></div>
        <p class="status" :class="{ 'is-processing': isAnalysisPending }" role="status"><span v-if="isAnalysisPending" class="activity-spinner" aria-hidden="true"></span>{{ status }}</p><p v-if="error" class="error">{{ error }}</p>
        <details class="analysis-settings" :open="!transcript.length">
          <summary>分析与任务设置</summary>
          <div class="analysis-settings-content">
        <label class="mode-picker">画面分析方式 <select v-model="visualAnalysisMode"><option value="both">语音文字＋每页代表图</option><option value="ocr_only">语音文字＋OCR 文字</option></select></label>
        <div class="advanced-options">
          <button type="button" class="advanced-toggle" :aria-expanded="advancedOpen" aria-controls="advanced-settings" @click="advancedOpen = !advancedOpen">{{ advancedOpen ? '收起高级选项' : '高级选项' }}</button>
          <div v-if="advancedOpen" id="advanced-settings" class="advanced-fields">
          <div class="advanced-row">
            <span id="coarse-sample-label">粗选采样间隔</span>
            <div class="sampling-options" role="group" aria-labelledby="coarse-sample-label">
              <button v-for="seconds in [2, 3, 4]" :key="seconds" type="button" :aria-pressed="coarseSampleSeconds === seconds" :disabled="isAnalysisPending" @click="coarseSampleSeconds = seconds">{{ seconds }} 秒{{ seconds === 2 ? '（默认）' : '' }}</button>
            </div>
          </div>
          <p class="advanced-help">间隔越长，扫描预览帧越少，但可能漏掉短暂出现的公式、表格或板书。仅影响新分析；重试沿用原任务设置。</p>
          <div class="advanced-row">
            <label for="coarse-change-percent">粗选画面变化阈值</label>
            <span class="help-tooltip" tabindex="0" aria-label="粗选画面变化阈值说明">?
              <span role="tooltip">按所选采样间隔比较画面。相邻画面变化区域超过所选比例时，保留候选截图；渐进书写另有保留规则。默认 2%。数值越低通常候选图越多，越不容易漏掉小变化；越高则候选图越少，但可能漏掉新画面。此值只影响第一轮粗选。</span>
            </span>
            <select id="coarse-change-percent" v-model="coarseChangePercent">
              <option value="0.5">0.5%</option><option value="1">1%</option>
              <option value="2">2%（默认）</option><option value="3">3%</option>
            </select>
          </div>
          </div>
        </div>
        <div class="restore"><label for="analysis-id">已有分析编号</label><div class="actions"><input id="analysis-id" v-model="existingJobId" placeholder="粘贴任务编号" /><button class="secondary" :disabled="!existingJobId.trim() || isAnalysisPending" @click="loadExistingAnalysis">读取结果</button></div><small>已分析过的视频可直接读取结果；播放原片段时仍需选择本地视频。</small></div>
        <button v-if="failedJobId" class="secondary" :disabled="isAnalysisPending" @click="retryAnalysis">重试这次分析</button>
        <button v-if="transcript.length && existingJobId && (!mindMap || mindMap.status === 'failed')"
          class="secondary" :disabled="generatingMindMap" @click="generateExistingMindMap(false)">
          {{ generatingMindMap ? '正在生成导图…' : mindMap ? '重试生成导图' : '从已有转写生成导图' }}
        </button>
        <button v-if="mindMap?.status === 'completed' && existingJobId" class="secondary"
          :disabled="generatingMindMap" @click="generateExistingMindMap(true)">
          {{ generatingMindMap ? '正在重新生成…' : '重新生成导图' }}
        </button>
          </div>
        </details>
        <details v-if="transcript.length || pageGroups.length || visualEvidence.length" class="full-analysis">
          <summary>查看完整分析记录 <span>OCR 原文、页面理解与候选截图</span></summary>
        <div class="evidence-workbench">
        <div v-if="transcript.length" class="points transcript-pane"><h3>同步字幕 <small>点击原文回放</small></h3><div ref="transcriptList" class="transcript-list">
          <button v-for="segment in transcript" :id="`transcript-${segment.id}`" :key="segment.id" class="point"
            :class="{ 'active-segment': segment.id === activeSegmentId }" @click="seekTo(segment.startMs, segment.id)">
            <span class="time">{{ new Date(segment.startMs).toISOString().slice(11, 19) }}</span>
            <span>{{ segment.text }}</span>
          </button>
        </div></div>
        <div v-if="pageGroups.length" class="points slides-pane"><h3>对应课件 <small>{{ pageGroups.length }} 页</small></h3>
          <div v-if="activeSlide" class="current-slide"><img v-if="activeSlide.representativeFrameTimesMs.length && !unavailableFrames.has(activeSlide.representativeFrameTimesMs[0])" loading="lazy" :src="`${apiBase}/transcriptions/${existingJobId}/frames/${activeSlide.representativeFrameTimesMs[0]}`" :alt="`第 ${activeSlide.pageIndex} 页课件画面`" @error="markFrameUnavailable(activeSlide.representativeFrameTimesMs[0])" /><p>第 {{ activeSlide.pageIndex }} 页 · {{ activeSlide.imageAnalysis?.title || activeSlide.textAnalysis?.title || '课程画面' }}</p></div>
          <details v-for="page in pageGroups" :key="page.pageIndex" class="visual-frame">
            <summary><span class="time">{{ formatTime(page.firstFrameTimeMs) }}</span>第 {{ page.pageIndex }} 页 · {{ page.imageAnalysis?.title || page.textAnalysis?.title || page.ocrLines.slice(0, 2).map(line => line.text).join(' · ') || '画面内容' }}<span v-if="page.imageAnalysis?.status === 'failed' || page.textAnalysis?.status === 'failed'"> · 本页理解失败</span><span v-if="page.imageAnalysis?.status === 'inferred' || page.textAnalysis?.status === 'inferred'"> · 含推导内容</span><span v-if="page.imageAnalysis?.status === 'unverified' || page.textAnalysis?.status === 'unverified'"> · 部分内容未核实 ？</span></summary>
            <div class="actions page-actions"><button class="secondary" @click="seekTo(page.firstFrameTimeMs)">从本页开始播放</button><button class="secondary" @click="seekTo(page.representativeFrameTimesMs[0] ?? page.firstFrameTimeMs)">跳到代表画面</button></div>
            <img v-for="timeMs in page.representativeFrameTimesMs" :key="timeMs" loading="lazy" :src="`${apiBase}/transcriptions/${existingJobId}/frames/${timeMs}`" :alt="`${formatTime(timeMs)} 的课程画面`" />
            <div class="evidence-columns"><section><h4>本页 OCR 文字</h4><p v-if="!page.ocrLines.length">未识别出文字</p><p v-for="line in page.ocrLines" :key="`${line.sourceFrameTimeMs}-${line.sourceBlockIndex}`"><button class="text-link" @click="seekTo(line.sourceFrameTimeMs)">{{ formatTime(line.sourceFrameTimeMs) }}</button> {{ line.text }}</p></section>
              <section v-if="page.imageAnalysis"><h4>语音＋图片理解</h4><p class="analysis-content">{{ page.imageAnalysis.content }}</p><p v-if="page.imageAnalysis.visualElements.length">图表/图形：{{ page.imageAnalysis.visualElements.join('；') }}</p><p v-if="page.imageAnalysis.uncertainties.length">待核实：{{ page.imageAnalysis.uncertainties.join('；') }}</p></section>
              <section v-else-if="page.textAnalysis"><h4>语音＋OCR 文字理解</h4><p class="analysis-content">{{ page.textAnalysis.content }}</p><p v-if="page.textAnalysis.visualElements.length">图表/图形：{{ page.textAnalysis.visualElements.join('；') }}</p><p v-if="page.textAnalysis.uncertainties.length">待核实：{{ page.textAnalysis.uncertainties.join('；') }}</p></section>
              <section v-else><h4>本页理解</h4><p>这份结果尚无页面理解内容。</p></section>
            </div>
            <details class="source-frames"><summary>查看本页 {{ page.memberFrameTimesMs.length }} 张原始候选截图</summary><div v-for="timeMs in page.memberFrameTimesMs" :key="timeMs"><button class="text-link" @click="seekTo(timeMs)">{{ formatTime(timeMs) }}</button> {{ frameAt(timeMs)?.ocrBlocks.map(block => block.text).join(' · ') || '无 OCR 文字' }}<img loading="lazy" :src="`${apiBase}/transcriptions/${existingJobId}/frames/${timeMs}`" :alt="`${formatTime(timeMs)} 的原始候选截图`" /></div></details>
          </details>
          <p v-if="review?.resampledTimesMs?.length" class="status">Agent 补采了 {{ review.resampledTimesMs.length }} 张画面。</p>
        </div>
        <div v-else-if="visualEvidence.length" class="points slides-pane"><h3>PPT 候选画面（旧任务）</h3>
          <div v-if="activeLegacyFrame && !unavailableFrames.has(activeLegacyFrame.frameTimeMs)" class="current-slide"><img loading="lazy" :src="`${apiBase}/transcriptions/${existingJobId}/frames/${activeLegacyFrame.frameTimeMs}`" :alt="`${formatTime(activeLegacyFrame.frameTimeMs)} 的课程画面`" @error="markFrameUnavailable(activeLegacyFrame.frameTimeMs)" /><p>{{ formatTime(activeLegacyFrame.frameTimeMs) }} · {{ activeLegacyFrame.imageAnalysis?.title || '对应课程画面' }}</p></div>
          <details v-for="frame in visualEvidence" :key="frame.frameTimeMs" class="visual-frame">
            <summary><span class="time">{{ new Date(frame.frameTimeMs).toISOString().slice(11, 19) }}</span> {{ frame.imageAnalysis?.title || frame.ocrBlocks.slice(0, 2).map(block => block.text).join(' · ') || '候选画面' }}<span v-if="frame.imageAnalysis?.status === 'failed'"> · 图片理解失败</span></summary>
            <button class="secondary" @click="seekTo(frame.frameTimeMs)">跳到这段视频</button>
            <img v-if="frame.imageAnalysis" loading="lazy" :src="`${apiBase}/transcriptions/${existingJobId}/frames/${frame.frameTimeMs}`" :alt="`${frame.frameTimeMs} 毫秒时的课程画面`" />
            <div class="evidence-columns">
              <section><h4>OCR 原文</h4><p>{{ frame.ocrBlocks.map(block => block.text).join(' · ') || '未识别出文字' }}</p></section>
              <section v-if="frame.imageAnalysis"><h4>图片理解</h4><p>{{ frame.imageAnalysis.content }}</p><p v-if="frame.imageAnalysis.visualElements.length">图表/图形：{{ frame.imageAnalysis.visualElements.join('；') }}</p><p v-if="frame.imageAnalysis.uncertainties.length">未看清：{{ frame.imageAnalysis.uncertainties.join('；') }}</p></section>
              <section v-else><h4>图片理解</h4><p>旧任务未进行图片分析</p></section>
            </div>
          </details>
          <p v-if="review?.resampledTimesMs?.length" class="status">Agent 补采了 {{ review.resampledTimesMs.length }} 张画面。</p>
        </div>
        </div>
        </details>
      </div>
    </section>
    <MindMapDialog v-if="expandedMap && mindMap?.root.children.length" :root="mindMap.root" @close="expandedMap = false" @select="selectExpandedMindNode" />
    <VideoWorkspace v-if="workspaceOpen" :src="videoUrl" :filename="filename" :model-value="ignoredRegion" :analysis-region="analysisRegion" @update:analysis-region="saveAnalysisRegion" :time-ms="currentPlaybackMs" :checking="checkingMedia" @close="workspaceOpen=false" @select-file="chooseVideo" @update:model-value="saveIgnoredRegion" />
  </main>
</template>
