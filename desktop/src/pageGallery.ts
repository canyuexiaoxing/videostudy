export function groupFrameTimes(page:{memberFrameTimesMs?:number[];representativeFrameTimesMs?:number[];firstFrameTimeMs?:number}):number[]{
  const times=[...new Set([...(page.memberFrameTimesMs??[]),...(page.representativeFrameTimesMs??[])])]
    .filter(time=>Number.isSafeInteger(time)&&time>=0).sort((a,b)=>a-b)
  return times.length?times:Number.isSafeInteger(page.firstFrameTimeMs)&&page.firstFrameTimeMs!>=0?[page.firstFrameTimeMs!]:[]
}
export function pageNearTime<T extends {firstFrameTimeMs:number}>(pages:T[],timeMs:number):T|undefined{
  const sorted=[...pages].sort((a,b)=>a.firstFrameTimeMs-b.firstFrameTimeMs)
  return [...sorted].reverse().find(page=>page.firstFrameTimeMs<=timeMs)??sorted[0]
}
