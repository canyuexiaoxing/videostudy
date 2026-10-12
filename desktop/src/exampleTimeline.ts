import type {MindMapNode, MindMapEvidence} from './mindMap'
type Segment={id:string;startMs:number;endMs:number;text:string}
const digits:Record<string,number>={'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
function number(value:string){if(/^\d+$/.test(value))return Number(value);if(value.includes('十')){const [l,r]=value.split('十');return (digits[l!]??1)*10+(digits[r!]??0)}return digits[value]??0}
export function questionOpening(text:string):number|null{
 text=text.replace(/\s+/g,'')
 const m=/(?:第|题)([0-9一二三四五六七八九十百]+)(?:题|体|个)/.exec(text.slice(0,40))
 if(m){
  const prefix=text.slice(0,m.index),suffix=text.slice(m.index+m[0].length)
  if(/回到|回顾|刚才|不是|前面|上一个/.test(prefix)||/^的(?:方法|结论|结果|答案|思路|做法)/.test(suffix))return null
  if(/再来|再看|来看|往下看|接下来|下下|一下看/.test(prefix)||(m.index===0&&/^开始/.test(suffix)))return number(m[1]!)||null
 }
 const prefix=text.slice(0,32)
 if(/回到|回顾|刚才|前面|上一个/.test(prefix))return null
 if(/(?:再来|来看|接下来|看)(?:一?道)?下一题/.test(prefix))return -1
 if(/(?:(?:来看|下面看|接下来(?:看)?)(?:这道|这个)(?:例题|题目)|(?:来看|再看|下面看|接下来(?:看)?|再来(?:做)?)(?:新的|新一道|一道|另一个|另一道)(?:例题|题目|题|例子))/.test(prefix))return -1
 return null
}

export function groupExamples(examples:MindMapNode[]|null|undefined,segments:Segment[]):MindMapNode[]{
 if(!examples?.length)return []
 const ordered=[...segments].sort((a,b)=>a.startMs-b.startMs)
 const markers:{source:Segment;number:number|null}[]=[];let last:number|null=null
 for(const source of ordered){const n=questionOpening(source.text);if(n!==null&&(n===-1||n!==last)){markers.push({source,number:n});last=n}}
 if(!markers.length)return examples
 const first=[...examples].sort((a,b)=>a.startMs-b.startMs)[0]!,source=ordered.find(s=>s.id===first.evidenceRefs[0]?.sourceId)
 if(!source)return examples
 if(markers[0]!.source.startMs>first.startMs)markers.unshift({source,number:null})
 const groups=new Map<number,{refs:Map<string,MindMapEvidence>;nodes:Map<string,MindMapNode>}>()
 for(const node of [...examples].sort((a,b)=>a.startMs-b.startMs)){
  for(let j=0;j<markers.length;j++)if(node.startMs<=markers[j]!.source.startMs&&markers[j]!.source.startMs<node.endMs){if(!groups.has(j))groups.set(j,{refs:new Map(),nodes:new Map()});groups.get(j)!.nodes.set(node.id,node)}
  for(const ref of node.evidenceRefs){
  let index=0;for(let j=0;j<markers.length;j++){if(markers[j]!.source.startMs>ref.startMs)break;index=j}
  if(!groups.has(index))groups.set(index,{refs:new Map(),nodes:new Map()});const g=groups.get(index)!;g.refs.set(ref.sourceId,{...ref});g.nodes.set(node.id,node)
 }
 }
 return [...groups.entries()].sort(([a],[b])=>a-b).map(([index,g])=>{
  const {source:s,number:n}=markers[index]!,hasRefs=g.refs.size>0;g.refs.set(s.id,{sourceType:'transcript',sourceId:s.id,startMs:s.startMs,endMs:s.endMs,quote:s.text})
  const refs=[...g.refs.values()].sort((a,b)=>a.startMs-b.startMs),nodes=[...g.nodes.values()].sort((a,b)=>a.startMs-b.startMs)
  const representative=nodes.find(v=>v.startMs<=s.startMs&&s.startMs<v.endMs)??nodes[0]!
  let title=representative.title.replace(/^例题\s*[0-9一二三四五六七八九十]*[：:]\s*/,'');if(n&&n>0)title=hasRefs&&title!==`例题 ${n}`?`例题 ${n}：${title}`:`例题 ${n}`
  return {id:`question_${s.id}`,title,startMs:refs[0]!.startMs,endMs:Math.max(...refs.map(r=>r.endMs)),evidenceRefs:refs,children:[]}
 })
}
