<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { API_ORIGIN } from './apiOrigin'
import { formatBytes, modelPercent, runtimeError } from './nativeRuntime'
import type { RuntimeMode, RuntimeStatus } from './nativeRuntime'
const emit = defineEmits<{close: []}>()
const bridge = window.framewiseDesktop
const dialog = ref<HTMLDialogElement | null>(null)
const status = ref<RuntimeStatus | null>(null), busy = ref(false), notice = ref(''), error = ref('')
const mode = ref<RuntimeMode>('auto'), apiKey = ref(''), model = ref('deepseek-flash'), baseUrl = ref('https://api.deepseek.com')
let timer: ReturnType<typeof setInterval> | undefined, alive = true, refreshing = false
const phase = computed(() => ({starting:'正在启动',ready:'可以开始学习',error:'启动遇到问题',stopped:'服务已停止',missing_runtime:'缺少运行环境'}[status.value?.phase || ''] || '正在检查本机环境'))
const modelState = computed(() => ({ready:'模型已就绪',installed:'模型已就绪',missing:'首次使用需要准备模型',absent:'首次使用需要准备模型',corrupt:'模型需要修复，请重试下载或重新导入',downloading:'正在下载模型',installing:'正在准备模型',error:'模型准备未完成',failed:'模型准备未完成',cancelled:'模型准备已取消'}[status.value?.models?.state || ''] || '正在检查模型'))
const downloading = computed(() => ['downloading','installing','preparing'].includes(status.value?.models?.state || ''))
const percent = computed(() => {
 const explicit = modelPercent(status.value?.models?.progress)
 if (explicit !== undefined) return explicit
 const files = status.value?.models?.files || []
 const total = files.reduce((sum, file) => sum + (file.size || 0), 0)
 if (!total) return undefined
 const completed = files.reduce((sum, file) => sum + (file.state === 'ready' ? file.size || 0 : file.downloaded || 0), 0)
 return modelPercent({completed,total})
})
const modules = computed(() => Object.entries(status.value?.hardware?.modules || {}).map(([name, value]) => ({name: ({asr:'语音识别',ocr:'文字识别',detector:'人物检测',yolo:'人物检测',whisper:'语音识别'} as Record<string,string>)[name] || name, ...(typeof value === 'string' ? {device:value} : value)})))
const idle = computed(() => !busy.value && !status.value?.metrics?.busy && !downloading.value)
function reasonText(reason?: string) {
 const reasons: Record<string,string> = {gpu_unavailable:'未发现可用 GPU，请选择自动或 CPU 模式。',gpu_unavailable_cpu_fallback:'GPU 不可用，自动模式已使用 CPU。',missing_models:'模型尚未准备完成，请下载或导入离线模型。',runtime_unavailable:'此模块运行环境不可用，请检查安装或导出诊断。',gpu_probe_failed:'GPU 检查未完成，请导出诊断或选择 CPU 模式。',cuda_unavailable:'CUDA 运行环境不可用，已使用 CPU。',cuda_missing:'CUDA 运行环境不可用，已使用 CPU。',insufficient_memory:'显存不足，已使用 CPU。',gpu_memory_insufficient:'显存不足，已使用 CPU。',cpu_selected:'已按设置使用 CPU。',unsupported_gpu:'当前 GPU 不支持此模块，已使用 CPU。',module_cpu_only:'此模块使用 CPU。'}
 return reason ? reasons[reason] || '当前模块使用兼容设备，详情可查看诊断。' : ''
}
async function refresh(initial = false) {
 if (!bridge || refreshing) return
 refreshing = true
 try { const data = await bridge.status(); if (!alive) return; status.value = data
   if (initial) { mode.value = data.settings?.mode || 'auto'; model.value = data.settings?.model || 'deepseek-flash'; baseUrl.value = data.settings?.baseUrl || 'https://api.deepseek.com' }
 } catch { if (alive) error.value = '暂时无法读取本机服务状态，请重试或导出诊断。' } finally { refreshing = false }
}
async function run(action: () => Promise<unknown>, success: string, reload = false) {
 if (busy.value) return
 busy.value = true; error.value = ''; notice.value = ''
 try { const result = await action() as {ok?:boolean;error?:string;cancelled?:boolean;apiOrigin?:string} | undefined
   if (!alive) return
   if (result?.cancelled) { notice.value='操作已取消。'; return }
   if (result?.ok === false || result?.error) { error.value = runtimeError(result.error); return }
   notice.value = success
   await refresh()
   if (reload && status.value?.apiOrigin && status.value.apiOrigin !== API_ORIGIN) window.location.reload()
 } catch { if (alive) error.value = '操作未完成，请重试或导出诊断。' } finally { busy.value = false }
}
async function save() {
 if (!bridge) return
 const nextKey = apiKey.value.trim()
 await run(() => bridge.saveSettings({mode:mode.value, model:model.value.trim(), baseUrl:baseUrl.value.trim(), ...(nextKey ? {apiKey:nextKey} : {})}), '设置已保存，后台已按新设置启动。')
 apiKey.value = ''
}
onMounted(() => { dialog.value?.showModal(); void refresh(true); if (bridge) timer = setInterval(() => void refresh(), 1800) })
onBeforeUnmount(() => { alive = false; if (timer) clearInterval(timer); apiKey.value = '' })
</script>
<template>
<dialog ref="dialog" class="runtime-dialog" aria-labelledby="runtime-title" @cancel.prevent="!busy && emit('close')">
 <header><div><h2 id="runtime-title">本机设置</h2><p>课程保存在本机。首次使用，准备模型并配置 AI 服务即可开始。</p></div><button class="secondary" type="button" :disabled="busy" @click="emit('close')">关闭</button></header>
 <template v-if="bridge">
  <section aria-label="运行状态"><div class="runtime-heading"><h3>本机服务</h3><span class="runtime-badge" role="status">{{ phase }}</span></div><p v-if="status?.error" class="runtime-error">{{ runtimeError(status.error) }}</p>
   <div class="runtime-actions"><button class="secondary" :disabled="busy" @click="run(() => bridge!.start(), '正在启动本机服务。', true)">启动 / 重试</button><button class="secondary" :disabled="!idle" @click="run(() => bridge!.restart(), '服务已重新启动。', true)">重启服务</button></div>
  </section>
  <section><h3>计算设备</h3><p>自动模式优先使用 GPU；各模块独立检查支持情况，需要时回退到 CPU。仅 GPU 模式会在 GPU 不可用时提示错误。</p><label class="runtime-field">运行模式<select v-model="mode" :disabled="busy"><option value="auto">自动 · GPU 优先（推荐）</option><option value="gpu">仅 GPU · 不可用时提示错误</option><option value="cpu">仅使用 CPU</option></select></label>
   <div v-for="item in modules" :key="item.name" class="runtime-device"><strong>{{ item.name }}</strong><span>{{ item.available === false ? '未就绪 · ' : '' }}{{ item.device === 'cuda' ? 'GPU' : item.device === 'cpu' ? 'CPU' : item.device || '正在检查' }}</span><small v-if="item.reason || item.fallbackReason">{{ reasonText(item.fallbackReason || item.reason) }}</small></div><p v-if="!modules.length">服务启动后显示各模块使用的设备及回退原因。</p>
  </section>
  <section><div class="runtime-heading"><h3>本地模型</h3><span>{{ modelState }}</span></div><p>语音识别、课件文字识别和人物检测在本机运行。首次下载可能需要一些时间，也可导入离线模型。</p><progress v-if="downloading || percent !== undefined" :value="percent" max="100" aria-label="模型准备进度"></progress><p v-if="percent !== undefined" role="status">{{ Math.round(percent) }}%</p><ul v-if="status?.models?.files?.length" class="runtime-files"><li v-for="file in status.models.files" :key="file.id"><span>{{ file.id }}</span><span>{{ file.state === 'ready' ? '已就绪' : file.state === 'downloading' ? formatBytes(file.downloaded) + ' / ' + formatBytes(file.size) : file.state === 'corrupt' ? '需要修复' : '待准备' }}</span></li></ul><div class="runtime-actions"><button class="secondary" :disabled="busy || downloading" @click="run(() => bridge!.installModels(), '已开始准备模型。')">下载 / 重试</button><button v-if="downloading" class="secondary" :disabled="busy" @click="run(() => bridge!.cancelModels(), '已取消模型下载。')">取消下载</button><button class="secondary" :disabled="busy || downloading" @click="run(() => bridge!.importModels(), '离线模型已导入。')">导入离线模型</button></div></section>
  <section><h3>DeepSeek 服务</h3><p v-if="status?.error==='runtime_key_unavailable'" class="runtime-error" role="alert">{{ runtimeError(status.error) }}</p><p>AI 解读、导图与练习需要模型服务。密钥由系统安全存储保存，保存后不会回显。留空可保留原密钥。</p><label class="runtime-field">API 密钥 <span>{{ status?.settings?.hasKey ? '已安全保存' : '尚未配置' }}</span><input v-model="apiKey" type="password" autocomplete="new-password" spellcheck="false" placeholder="输入新的 API 密钥" :disabled="busy" /></label><label class="runtime-field">模型名称<input v-model="model" autocomplete="off" :disabled="busy" /></label><label class="runtime-field">服务地址<input v-model="baseUrl" type="url" autocomplete="off" :disabled="busy" /></label><button class="run" :disabled="busy" @click="save">保存设置</button></section>
  <section><h3>数据与维护</h3><p>备份保存课程资料，恢复会替换本机数据；请先备份当前资料。恢复和清理需要所有课程任务空闲。原视频仍需自行保管。</p><div class="runtime-actions"><button class="secondary" :disabled="!idle" @click="run(() => bridge!.exportBackup(), '备份已导出。')">导出备份</button><button class="secondary" :disabled="!idle" @click="run(() => bridge!.restoreBackup(), '备份已恢复，请重新打开课程。', true)">恢复备份</button><button class="secondary" :disabled="busy" @click="run(() => bridge!.exportDiagnostics(), '诊断已导出，不包含 API 密钥。')">导出诊断</button><button class="secondary" :disabled="busy" @click="run(() => bridge!.openDataDirectory(), '已打开数据目录。')">打开数据目录</button></div><p>可清理缓存：{{ formatBytes(status?.metrics?.cacheBytes) }}。仅清理可重新生成的临时文件，保留课程、笔记和已安装模型。</p><button class="secondary" :disabled="!idle" @click="run(() => bridge!.clearCache(), '临时缓存已清理。')">清理临时缓存</button></section>
 </template>
 <section v-else><h3>浏览器预览模式</h3><p>本机运行环境、设备和密钥由桌面应用管理。当前页面继续连接本地开发服务，学习功能可照常使用。</p></section>
 <p v-if="error" class="runtime-error" role="alert">{{ error }}</p><p v-if="notice" class="runtime-notice" role="status">{{ notice }}</p>
</dialog>
</template>
<style scoped>
.runtime-dialog{width:min(680px,94vw);max-height:88vh;box-sizing:border-box;padding:26px;border:1px solid #d9e3fa;border-radius:20px;background:#f9fbff;color:#233758;box-shadow:0 24px 80px #13275238}.runtime-dialog::backdrop{background:#101d3c88}.runtime-dialog header,.runtime-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}.runtime-dialog h2{margin:0;font-size:22px}.runtime-dialog h3{margin:0 0 12px;font-size:16px}.runtime-dialog p{font-size:13px;line-height:1.8;color:#6b7e9e}.runtime-dialog section{padding:20px 0;border-top:1px solid #e1e8f7}.runtime-dialog header{padding-bottom:16px}.runtime-badge{color:#3564ac;background:#edf3ff;border-radius:20px;padding:5px 12px;font-size:12px}.runtime-heading>span{font-size:12px}.runtime-field{display:block;font-size:13px;margin:14px 0}.runtime-field>span{font-size:12px;color:#6b7e9e;margin-left:8px}.runtime-field input,.runtime-field select{display:block;width:100%;box-sizing:border-box;border:1px solid #ccd8ef;border-radius:9px;background:#fff;color:#233758;padding:10px 12px;margin-top:7px;font:inherit}.runtime-actions{display:flex;gap:10px;flex-wrap:wrap}.runtime-dialog button{cursor:pointer}.runtime-dialog button:disabled{opacity:.5;cursor:default}.runtime-dialog progress{width:100%;accent-color:#547ce5}.runtime-files{padding:0;list-style:none;font-size:12px;color:#6b7e9e}.runtime-files li{display:flex;justify-content:space-between;gap:16px;padding:7px 0;overflow-wrap:anywhere}.runtime-device{display:grid;grid-template-columns:1fr 1fr;font-size:13px;gap:7px;padding:12px;background:#edf3ff;border-radius:9px;margin:8px 0}.runtime-device small{grid-column:1/-1;color:#6b7e9e}.runtime-dialog .runtime-error{color:#a34646}.runtime-dialog .runtime-notice{color:#277758}@media(max-width:600px){.runtime-dialog{padding:18px}.runtime-heading{flex-wrap:wrap}}
</style>
