import { setApiOrigin, disableApiOrigin } from './apiOrigin.ts'
export type RuntimeMode = 'auto' | 'gpu' | 'cpu'
export type RuntimeModule = { device?: string; reason?: string; fallbackReason?: string; available?: boolean }
export type RuntimeStatus = {
  phase: string; apiOrigin?: string; error?: string
  settings?: { mode?: RuntimeMode; hasKey?: boolean; model?: string; baseUrl?: string }
  hardware?: { modules?: Record<string, RuntimeModule | string>; gpu?: unknown }
  models?: { state?: string; files?: {id: string; state: string; downloaded?: number; size?: number}[]; progress?: number | { completed?: number; total?: number; percent?: number; bytes?: number; totalBytes?: number } }
  paths?: { dataDir?: string }; metrics?: { cacheBytes?: number; busy?: boolean }; [key: string]: unknown
}
export type DesktopBridge = {
  status(): Promise<RuntimeStatus>
  saveSettings(settings: { mode: RuntimeMode; apiKey?: string; model?: string; baseUrl?: string }): Promise<unknown>
  start(): Promise<unknown>; restart(): Promise<unknown>; installModels(): Promise<unknown>; cancelModels(): Promise<unknown>
  exportBackup(): Promise<unknown>; restoreBackup(): Promise<unknown>; exportDiagnostics(): Promise<unknown>
  clearCache(): Promise<unknown>; openDataDirectory(): Promise<unknown>; importModels(): Promise<unknown>
}
declare global { interface Window { framewiseDesktop?: DesktopBridge } }
export async function bootstrapRuntime(bridge?: Pick<DesktopBridge, 'status'>, timeoutMs = 2500): Promise<RuntimeStatus | null> {
  if (!bridge) return null
  disableApiOrigin()
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    const status = await Promise.race([bridge.status(), new Promise<null>(resolve => { timer = setTimeout(() => resolve(null), timeoutMs) })])
    if (status?.apiOrigin) setApiOrigin(status.apiOrigin)
    return status
  } catch { return null } finally { if (timer) clearTimeout(timer) }
}
export function unavailableAnalysisModules(status: RuntimeStatus | null, personMode = 'off'): string[] {
 const modules = status?.hardware?.modules || {}
 return Object.entries(modules).filter(([name, module]) => {
  if (['yolo', 'person', 'detector'].includes(name) && personMode !== 'adjacent') return false
  return typeof module === 'object' && module?.available === false
 }).map(([name]) => name)
}
export function runtimeError(code?: string): string {
  const messages: Record<string, string> = {
    runtime_missing: '本机运行环境尚未安装，请使用完整安装包或打开诊断检查安装。', missing_runtime: '本机运行环境尚未安装，请使用完整安装包。',
    models_missing: '首次使用需要准备模型，可在线下载或导入离线模型。', download_failed: '模型下载未完成，请重试或导入离线模型。',
    runtime_start_failed: '本机服务启动失败，请重试或导出诊断。', runtime_agent_timeout: '本地分析服务启动超时，请重试；仍失败时可打开数据目录或导出诊断。', runtime_initialization_failed: '本机环境初始化失败，原设置和密钥已保留。请先打开数据目录备份 settings.json，再导出诊断排查；重新安装不会自动修复用户设置。', renderer_restore_recovery_required: '备份恢复尚未完成，已暂停启动以保护数据。请打开数据目录保留恢复副本，并导出诊断。', restore_recovery_required: '检测到未完成的备份恢复，请保留数据目录中的恢复副本并导出诊断。', runtime_timeout: '本机服务启动超时，请重试或导出诊断。',
    runtime_busy: '仍有课程任务正在处理，请完成后再操作。', course_busy: '仍有课程任务正在处理，请完成后再操作。',
    backup_busy: '仍有任务正在处理，请等待空闲后备份或恢复。', restore_busy: '恢复需要所有任务空闲，请完成当前任务后再试。',
    invalid_backup: '备份未通过检查，请选择 Framewise 导出的有效备份。', key_storage_unavailable: '系统安全存储暂不可用，密钥尚未保存。',
    secure_storage_unavailable: '系统安全存储暂不可用，密钥尚未保存。', invalid_api_key: '密钥格式不正确，请重新输入。',
    insufficient_disk_space: '磁盘空间不足，请释放空间后重试。', model_checksum_mismatch: '模型校验未通过，请重新下载或选择正确的离线模型。',
    model_install_running: '模型已在准备中，请等待或取消后重试。', invalid_model_manifest: '安装包的模型清单不完整，请重新安装完整版本。',
    runtime_not_stopped: '数据维护需要服务停止并且任务空闲，请稍后重试。', quiescence_required: '请等待课程任务结束后再执行数据维护。',
    data_operation_running: '另一项数据操作仍在进行，请等待完成。', backup_checksum_mismatch: '备份校验未通过，未替换本机课程。',
    backup_destination_exists: '目标备份目录已存在，请选择新位置。', overlapping_backup_path: '请在应用数据目录之外选择备份位置。',
    invalid_settings: '设置未通过检查，请核对模型名称和服务地址。', cancelled: '操作已取消。'
  }
  return messages[code || ''] || '操作未完成，请重试；如仍失败，可导出诊断以定位问题。'
}
export function modelPercent(progress: unknown): number | undefined {
  if (typeof progress === 'number') return Number.isFinite(progress) ? Math.min(100, Math.max(0, progress)) : undefined
  if (!progress || typeof progress !== 'object') return undefined
  const p = progress as { percent?: number; completed?: number; total?: number; bytes?: number; totalBytes?: number }
  if (typeof p.percent === 'number') return modelPercent(p.percent)
  const done = p.bytes ?? p.completed, total = p.totalBytes ?? p.total
  return typeof done === 'number' && typeof total === 'number' && total > 0 ? modelPercent(done / total * 100) : undefined
}
export function formatBytes(bytes?: number): string {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes < 0) return '待统计'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}
