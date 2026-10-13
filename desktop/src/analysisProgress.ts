export type AnalysisProgress = {stage:string;completedStages:number;totalStages:number;completedUnits:number;totalUnits:number;phase?:string|null;readyGroups?:number|null;completedGroups?:number|null;totalGroups?:number|null;groupPhase?:string|null}
const stages:Record<string,number>={media:0,coverage:1,grouping:2,pages:3,groups:3,materials:4,saving:4}
const labels:Record<string,string>={media:'语音转写与截图筛选',coverage:'补采检查',grouping:'同页分组',pages:'页面解读',groups:'按组图文理解',materials:'思维导图生成',saving:'正在保存分析结果'}
export function progressView(state:string, value:AnalysisProgress|null){
 const valid=!!value&&Object.hasOwn(stages,value.stage)&&value.completedStages===stages[value.stage]&&value.totalStages===5&&[value.completedStages,value.completedUnits,value.totalUnits].every(Number.isSafeInteger)&&value.completedUnits>=0&&value.totalUnits>=value.completedUnits
 const p=valid?value:null
 const ratio=p?.stage==='saving'?.95:p?(p.completedStages+(p.totalUnits>0?p.completedUnits/p.totalUnits:0))/5:0
 let label=p?labels[p.stage]+(p.stage==='pages'||p.stage==='groups'?` · 已完成 ${p.completedUnits} / ${p.totalUnits} 页`:p.stage==='materials'?` · 已完成 ${p.completedUnits} / ${p.totalUnits} 项`:''): '正在准备分析…'
 if(p && Number.isSafeInteger(p.completedGroups) && Number.isSafeInteger(p.totalGroups) && p.completedGroups!>=0 && p.totalGroups!>=p.completedGroups!) {
  const phases:Record<string,string>={waiting_initial:'等待首批图文',analyzing:'分析组图文',linking:'衔接前后组',revising:'更新受影响组',completed:'组分析完成'}
  label+=` · ${phases[p.groupPhase??'']??'组图文'} ${p.completedGroups} / ${p.totalGroups} 组`
 }
 if(state==='completed')return {label:'分析完成',ratio:1,completed:5,indeterminate:false}
 if(state==='uploading')return {label:'正在上传视频…',ratio:0,completed:0,indeterminate:true}
 if(state==='reading')return {label:'正在读取分析进度…',ratio:0,completed:0,indeterminate:true}
 if(state==='queued')return {label:'等待分析任务…',ratio:0,completed:0,indeterminate:true}
 if(state==='failed'||state==='interrupted')return {label:(state==='failed'?'分析未完成':'进度查询或上传中断')+(p?` · ${label}`:''),ratio:Math.min(ratio,.95),completed:p?.completedStages??0,indeterminate:false}
 return {label,ratio:Math.min(ratio,.95),completed:p?.completedStages??0,indeterminate:!p}
}
