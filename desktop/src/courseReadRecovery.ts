import type {DesktopBridge} from './nativeRuntime.ts'
import type {RequestTicket} from './mediaBinding.ts'
function current(ticket:RequestTicket){if(!ticket.current()||ticket.signal.aborted)throw new DOMException('Aborted','AbortError')}
export function readDelay(ms:number,signal:AbortSignal):Promise<void>{return new Promise((resolve,reject)=>{
 if(signal.aborted){reject(new DOMException('Aborted','AbortError'));return}
 const abort=()=>{clearTimeout(timer);signal.removeEventListener('abort',abort);reject(new DOMException('Aborted','AbortError'))}
 const timer=setTimeout(()=>{signal.removeEventListener('abort',abort);resolve()},ms);signal.addEventListener('abort',abort,{once:true})
})}
async function bounded<T>(work:(signal:AbortSignal)=>Promise<T>,ticket:RequestTicket,ms:number):Promise<T>{
 current(ticket);const controller=new AbortController();let timer:ReturnType<typeof setTimeout>|undefined;let abort:()=>void=()=>{}
 try{return await Promise.race([new Promise<T>((_,reject)=>{
  abort=()=>{controller.abort();reject(new DOMException('Aborted','AbortError'))};ticket.signal.addEventListener('abort',abort,{once:true})
  timer=setTimeout(()=>{controller.abort();reject(new Error('查询响应超时'))},ms)
 }),work(controller.signal)]).then(value=>{current(ticket);return value})}
 finally{clearTimeout(timer);ticket.signal.removeEventListener('abort',abort)}
}
export async function waitForRuntimeReady(bridge:Pick<DesktopBridge,'status'>|undefined,ticket:RequestTicket,options:{expectedOrigin?:string;onWaiting?:()=>void;pollMs?:number;statusTimeoutMs?:number;timeoutMs?:number}={}):Promise<void>{
 current(ticket);if(!bridge)return
 const deadline=Date.now()+(options.timeoutMs??300000)
 while(Date.now()<deadline){
  current(ticket);let state
  try{state=await bounded(()=>bridge.status(),ticket,Math.min(options.statusTimeoutMs??3500,deadline-Date.now()))}catch{current(ticket)}
  if(state?.phase==='ready'){
   if(options.expectedOrigin && state.apiOrigin!==options.expectedOrigin)throw new Error('本机服务地址已变化，请重新打开软件后读取课程。')
   return
  }
  if(state && ['error','missing_runtime'].includes(state.phase))throw new Error('本机服务尚未启动或启动失败，请在设置中启动或重试。')
  options.onWaiting?.();await readDelay(Math.min(options.pollMs??1500,Math.max(1,deadline-Date.now())),ticket.signal)
 }
 throw new Error('等待本机服务启动超时，请在设置中检查后点击重试读取。')
}
class ReadFailure extends Error {retryable:boolean;constructor(status:number){super(`读取课程失败：HTTP ${status}`);this.retryable=[408,429,500,502,503,504].includes(status)}}
export async function readCourseJson<T>(url:string,ticket:RequestTicket,options:{fetcher?:typeof fetch;retryMs?:number;requestTimeoutMs?:number;onRetry?:(attempt:number)=>void}={}):Promise<T>{
 for(let attempt=0;attempt<3;attempt++){
  current(ticket)
  try{return await bounded(async signal=>{const response=await (options.fetcher??fetch)(url,{method:'GET',signal});if(!response.ok)throw new ReadFailure(response.status);return await response.json() as T},ticket,options.requestTimeoutMs??10000)}
  catch(error){current(ticket);if(error instanceof ReadFailure && !error.retryable || attempt===2)throw error;options.onRetry?.(attempt+1);await readDelay(options.retryMs??1000,ticket.signal)}
 }
 throw new Error('读取课程失败')
}
