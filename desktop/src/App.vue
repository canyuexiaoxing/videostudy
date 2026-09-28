<script setup lang="ts">
import { onUnmounted, ref } from 'vue'

type Point = { id: string; title: string; startMs: number; endMs: number; evidence: string }
type Job = { id: string; status: string; result?: { summary: string; points: Point[] }; error?: string }
type Segment = { id: string; startMs: number; endMs: number; text: string }
type OcrBlock = { text: string; score: number; polygon: number[][] }
type ImageAnalysis = { status: string; title: string; content: string; visualElements: string[]; uncertainties: string[] }
type VisualEvidence = { frameTimeMs: number; ocrBlocks: OcrBlock[]; imageAnalysis?: ImageAnalysis }
type OcrLine = { text: string; sourceFrameTimeMs: number; sourceBlockIndex: number }
type PageGroup = { pageIndex: number; firstFrameTimeMs: number; lastFrameTimeMs: number;
  memberFrameTimesMs: number[]; representativeFrameTimesMs: number[];
  decision: string; decisionReason: string; ocrLines: OcrLine[]; imageAnalysis?: ImageAnalysis; textAnalysis?: ImageAnalysis }
type Review = { status: string; resampledTimesMs: number[]; concerns: string[] }
type TranscriptionJob = { id: string; status: string; result?: { language: string; segments: Segment[]; visualEvidence?: VisualEvidence[]; pageGroups?: PageGroup[]; visualAnalysisMode?: 'ocr_only' | 'both'; ocrModelId?: string; imageModelId?: string; review?: Review }; error?: string }

const apiBase = 'http://127.0.0.1:18080/api'
const video = ref<HTMLVideoElement | null>(null)
const selectedFile = ref<File | null>(null)
const videoUrl = ref('')
const filename = ref('')
const fileSize = ref(0)
const status = ref('请选择本地视频')
const points = ref<Point[]>([])
const transcript = ref<Segment[]>([])
const visualEvidence = ref<VisualEvidence[]>([])
const pageGroups = ref<PageGroup[]>([])
const visualAnalysisMode = ref<'ocr_only' | 'both'>('both')
const coarseChangePercent = ref('2')
const advancedOpen = ref(false)
const review = ref<Review | null>(null)
const failedJobId = ref('')
const existingJobId = ref(localStorage.getItem('lastAnalysisId') ?? '')
const error = ref('')

function chooseVideo(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  selectedFile.value = file
  if (videoUrl.value) URL.revokeObjectURL(videoUrl.value)
  videoUrl.value = URL.createObjectURL(file)
  filename.value = file.name
  fileSize.value = file.size
  points.value = []
  transcript.value = []
  visualEvidence.value = []
  pageGroups.value = []
  review.value = null
  failedJobId.value = ''
  error.value = ''
  status.value = '本地视频已就绪；可上传进行分析'
}

async function waitForAnalysis(id: string) {
    for (let attempt = 0; attempt < 1800; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      const query = await fetch(`${apiBase}/transcriptions/${id}`)
      if (!query.ok) throw new Error(`查询转写状态失败：HTTP ${query.status}`)
      const job: TranscriptionJob = await query.json()
      status.value = job.status === 'queued' ? '等待分析任务…' : '正在分析…'
      if (job.status === 'failed') {
        failedJobId.value = id
        throw new Error(job.error || '分析失败')
      }
      if (job.status === 'completed') {
        transcript.value = job.result?.segments ?? []
        visualEvidence.value = job.result?.visualEvidence ?? []
        pageGroups.value = job.result?.pageGroups ?? []
        review.value = job.result?.review ?? null
        failedJobId.value = ''
        const pageStatuses = pageGroups.value.map(page =>
          (job.result?.visualAnalysisMode === 'ocr_only' ? page.textAnalysis : page.imageAnalysis)?.status)
        const completedCount = pageStatuses.filter(value => value === 'completed').length
        const inferredCount = pageStatuses.filter(value => value === 'inferred').length
        const unverifiedCount = pageStatuses.filter(value => value === 'unverified').length
        const routeName = job.result?.visualAnalysisMode === 'ocr_only' ? '语音＋OCR 文字理解' : '语音＋图片理解'
        status.value = `分析完成：转写 ${transcript.value.length} 段；候选画面 ${visualEvidence.value.length} 张、归为 ${pageGroups.value.length} 页；OCR ${job.result?.ocrModelId || '未记录'}；${routeName}确认 ${completedCount} 页、含推导 ${inferredCount} 页、待核实 ${unverifiedCount} 页`
        return
      }
    }
    throw new Error('等待分析超时')
}

async function runTranscription() {
  if (!selectedFile.value) return
  if (selectedFile.value.size > 2 * 1024 * 1024 * 1024) {
    error.value = '当前最多上传 2 GB'
    return
  }
  error.value = ''
  transcript.value = []
  visualEvidence.value = []
  pageGroups.value = []
  review.value = null
  failedJobId.value = ''
  status.value = '正在临时上传视频…'
  try {
    const form = new FormData()
    form.append('file', selectedFile.value)
    form.append('visualAnalysisMode', visualAnalysisMode.value)
    form.append('coarseChangePercent', coarseChangePercent.value)
    const response = await fetch(`${apiBase}/transcriptions`, { method: 'POST', body: form })
    if (!response.ok) throw new Error(`上传失败：HTTP ${response.status}`)
    const created: TranscriptionJob = await response.json()
    existingJobId.value = created.id
    localStorage.setItem('lastAnalysisId', created.id)
    await waitForAnalysis(created.id)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
    status.value = '分析未完成'
  }
}

async function loadExistingAnalysis() {
  const id = existingJobId.value.trim()
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
    error.value = '请输入有效的分析编号'
    return
  }
  error.value = ''
  status.value = '正在读取已保存的分析结果…'
  try {
    await waitForAnalysis(id)
    localStorage.setItem('lastAnalysisId', id)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
    status.value = '未能读取分析结果'
  }
}

async function retryAnalysis() {
  if (!failedJobId.value) return
  error.value = ''
  status.value = '正在重新分析保留的上传文件…'
  try {
    const id = failedJobId.value
    const response = await fetch(`${apiBase}/transcriptions/${id}/retry`, { method: 'POST' })
    if (!response.ok) throw new Error(`重试失败：HTTP ${response.status}`)
    await waitForAnalysis(id)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
    status.value = '分析未完成'
  }
}

async function runDemo() {
  if (!filename.value) return
  error.value = ''
  status.value = '正在创建课程与演示任务…'
  try {
    const courseResponse = await fetch(`${apiBase}/courses`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: filename.value, sizeBytes: fileSize.value }),
    })
    if (!courseResponse.ok) throw new Error(`创建课程失败：HTTP ${courseResponse.status}`)
    const course: { id: string } = await courseResponse.json()
    const jobResponse = await fetch(`${apiBase}/courses/${course.id}/jobs`, { method: 'POST' })
    if (!jobResponse.ok) throw new Error(`创建任务失败：HTTP ${jobResponse.status}`)
    const created: Job = await jobResponse.json()
    const resultResponse = await fetch(`${apiBase}/jobs/${created.id}`)
    if (!resultResponse.ok) throw new Error(`查询任务失败：HTTP ${resultResponse.status}`)
    const job: Job = await resultResponse.json()
    if (job.status !== 'completed' || !job.result) throw new Error(job.error || `任务状态：${job.status}`)
    points.value = job.result.points
    status.value = job.result.summary
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
    status.value = '接口演示失败'
  }
}

function seekTo(startMs: number) {
  if (!video.value) return
  video.value.currentTime = startMs / 1000
  void video.value.play().catch(() => { status.value = '已跳转，请点击播放器继续播放' })
}

function formatTime(timeMs: number) { return new Date(timeMs).toISOString().slice(11, 19) }
function frameAt(timeMs: number) { return visualEvidence.value.find(frame => frame.frameTimeMs === timeMs) }

onUnmounted(() => { if (videoUrl.value) URL.revokeObjectURL(videoUrl.value) })
</script>

<template>
  <main>
    <header><span class="eyebrow">VIDEOSTUDY · PROTOTYPE</span><h1>从课程片段回到原视频</h1><p>本地播放、真实语音转写与时间跳转。示例节点仍是固定数据，不代表 AI 分析。</p></header>
    <section class="workspace">
      <div class="panel player-panel">
        <div class="section-title"><h2>本地视频</h2><span>文件保留在你的电脑</span></div>
        <label class="file-picker">选择视频 <input type="file" accept="video/*,audio/*" @change="chooseVideo" /></label>
        <p class="filename">{{ filename || '尚未选择文件' }}</p>
        <video v-if="videoUrl" ref="video" :src="videoUrl" controls preload="metadata" />
        <div v-else class="empty-player">选择本地视频，即可在这里播放和按时间回看</div>
      </div>
      <div class="panel results-panel">
        <div class="section-title"><h2>分析结果</h2><span>接口联调版</span></div>
        <label class="mode-picker">画面分析方式 <select v-model="visualAnalysisMode"><option value="both">语音文字＋每页代表图</option><option value="ocr_only">语音文字＋OCR 文字</option></select></label>
        <div class="advanced-options">
          <button type="button" class="advanced-toggle" :aria-expanded="advancedOpen" aria-controls="advanced-settings" @click="advancedOpen = !advancedOpen">{{ advancedOpen ? '收起高级选项' : '高级选项' }}</button>
          <div v-if="advancedOpen" id="advanced-settings" class="advanced-row">
            <label for="coarse-change-percent">粗选画面变化阈值</label>
            <span class="help-tooltip" tabindex="0" aria-label="粗选画面变化阈值说明">?
              <span role="tooltip">每隔 2 秒比较一次画面。相邻画面变化区域超过所选比例时，保留候选截图；渐进书写另有保留规则。默认 2%。数值越低通常候选图越多，越不容易漏掉小变化；越高则候选图越少，但可能漏掉新画面。此值只影响第一轮粗选。</span>
            </span>
            <select id="coarse-change-percent" v-model="coarseChangePercent">
              <option value="0.5">0.5%</option><option value="1">1%</option>
              <option value="2">2%（默认）</option><option value="3">3%</option>
            </select>
          </div>
        </div>
        <div class="actions"><button class="run" :disabled="!filename" @click="runTranscription">上传并分析视频</button><button class="secondary" :disabled="!filename" @click="runDemo">运行接口演示</button></div>
        <div class="restore"><label for="analysis-id">已有分析编号</label><div class="actions"><input id="analysis-id" v-model="existingJobId" placeholder="粘贴任务编号" /><button class="secondary" :disabled="!existingJobId.trim()" @click="loadExistingAnalysis">读取结果</button></div><small>已分析过的视频可直接读取结果；播放原片段时仍需选择本地视频。</small></div>
        <button v-if="failedJobId" class="secondary" @click="retryAnalysis">重试这次分析</button>
        <p class="status">{{ status }}</p><p v-if="error" class="error">{{ error }}</p>
        <div v-if="points.length" class="points">
          <button v-for="point in points" :key="point.id" class="point" @click="seekTo(point.startMs)">
            <span class="time">{{ Math.floor(point.startMs / 60000).toString().padStart(2, '0') }}:{{ Math.floor(point.startMs / 1000) % 60 < 10 ? '0' : '' }}{{ Math.floor(point.startMs / 1000) % 60 }}</span>
            <span><strong>{{ point.title }}</strong><small>{{ point.evidence }}</small></span>
          </button>
        </div>
        <div v-if="transcript.length" class="points"><h3>带时间的转写稿</h3>
          <button v-for="segment in transcript" :key="segment.id" class="point" @click="seekTo(segment.startMs)">
            <span class="time">{{ new Date(segment.startMs).toISOString().slice(11, 19) }}</span>
            <span>{{ segment.text }}</span>
          </button>
        </div>
        <div v-if="pageGroups.length" class="points"><h3>PPT 页面（{{ pageGroups.length }} 页）</h3>
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
        <div v-else-if="visualEvidence.length" class="points"><h3>PPT 候选画面（旧任务）</h3>
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
    </section>
  </main>
</template>
