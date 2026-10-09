export type ReviewCitation = { sourceId: string; startMs: number; endMs?: number; quote: string }
export type ReviewTarget = ReviewCitation & { matched: boolean }
const ignored = new Set(['等于','就是','使用','计算','应该','这个','一个','进行','the','and','with'])
function terms(text: string): Set<string> {
  const tokens = new Set<string>()
  for (const run of text.toLowerCase().slice(0,1000).match(/[\u4e00-\u9fff]+|[a-z]+/g) ?? []) {
    if (/^[a-z]+$/.test(run)) { if (run.length > 2 && !ignored.has(run)) tokens.add(run); continue }
    for(let i=0;i<run.length-1;i++) { const term=run.slice(i,i+2); if(!ignored.has(term))tokens.add(term) }
  }
  return tokens
}
// Rank only verified question citations; lexical overlap is a recommendation, not a new diagnosis.
export function reviewTargets(citations: ReviewCitation[], nodeTitle: string, takeaway: string, selectedReason: string): ReviewTarget[] {
  const weighted = [[terms(nodeTitle),3],[terms(takeaway),2],[terms(selectedReason),1]] as const
  const seen=new Set<string>()
  const rows = citations.filter(ref=>{
    if(!ref || typeof ref.sourceId!=='string' || !ref.sourceId || seen.has(ref.sourceId) ||
      !Number.isSafeInteger(ref.startMs) || ref.startMs<0 || typeof ref.quote!=='string' || !ref.quote.trim() ||
      (ref.endMs!==undefined && (!Number.isSafeInteger(ref.endMs) || ref.endMs<=ref.startMs)))return false
    seen.add(ref.sourceId);return true
  }).map(ref=>{
    const quote=terms(ref.quote)
    const score=weighted.reduce((sum,[words,weight])=>sum+[...words].filter(word=>quote.has(word)).length*weight,0)
    return {ref,score}
  }).sort((a,b)=>b.score-a.score||a.ref.startMs-b.ref.startMs)
  return rows.map(({ref,score})=>({...ref,matched:score>0}))
}
