<script setup lang="ts">
import {computed,useId} from 'vue'
import MathText from './MathText.vue'
import type {Diagram,DiagramPoint,DiagramEdge,CircuitComponent} from './practiceDiagram'
const props=defineProps<{diagram:Diagram}>()
const marker='arrow-'+useId().replace(/:/g,'')
const colors=['#426aee','#a064d9','#20a18d','#e29a42','#d56882','#6b88b8']
const values=computed(()=>props.diagram.values??[])
const format=(value:number)=>Number.isFinite(value)?String(+value.toPrecision(4)):''
const points=computed(()=>Object.fromEntries((props.diagram.points??props.diagram.nodes??[]).map(p=>[p.id,p])))
const geom=computed(()=>{
 const list=Object.values(points.value);let xs=list.map(p=>p.x),ys=list.map(p=>p.y)
 for(const c of props.diagram.circles??[]){const p=points.value[c.center];if(p){xs.push(p.x-c.radius,p.x+c.radius);ys.push(p.y-c.radius,p.y+c.radius)}}
 const xmin=xs.length?Math.min(...xs):0,xmax=xs.length?Math.max(...xs):1,ymin=ys.length?Math.min(...ys):0,ymax=ys.length?Math.max(...ys):1,scale=Math.min(520/Math.max(.001,xmax-xmin),280/Math.max(.001,ymax-ymin))
 return {scale,xmid:(xmin+xmax)/2,ymid:(ymin+ymax)/2}
})
const gx=(x:number)=>320+(x-geom.value.xmid)*geom.value.scale
const gy=(y:number)=>205-(y-geom.value.ymid)*geom.value.scale
function p(id:string):DiagramPoint{return points.value[id]??{id,x:0,y:0}}
function component(c:CircuitComponent){const a=p(c.from),b=p(c.to),x=gx(a.x),y=gy(a.y),dx=gx(b.x)-x,dy=gy(b.y)-y,length=Math.hypot(dx,dy),angle=Math.atan2(dy,dx)*180/Math.PI,vertical=Math.abs(dy)>Math.abs(dx);return {transform:`translate(${x},${y}) rotate(${angle})`,angle,length,mid:length/2,width:Math.min(48,length*.52),x:x+dx/2+(vertical?(dy>0?28:-28):dy/Math.max(1,length)*26),y:y+dy/2+(vertical?4:-dx/Math.max(1,length)*26),anchor:vertical?(dy>0?'start':'end'):'middle'}}

function coil(c:CircuitComponent){const {mid,width}=component(c);return `M ${mid-width/2} 0 `+Array.from({length:4},()=>`c 0 -15 ${width/4} -15 ${width/4} 0`).join(' ')}
function anglePath(mark:{a:string;vertex:string;b:string}){const a=p(mark.a),v=p(mark.vertex),b=p(mark.b),x=gx(v.x),y=gy(v.y),start=Math.atan2(gy(a.y)-y,gx(a.x)-x),finish=Math.atan2(gy(b.y)-y,gx(b.x)-x);let delta=finish-start;while(delta>Math.PI)delta-=2*Math.PI;while(delta< -Math.PI)delta+=2*Math.PI;const radius=Math.min(28,Math.hypot(gx(a.x)-x,gy(a.y)-y)*.3,Math.hypot(gx(b.x)-x,gy(b.y)-y)*.3);return {d:`M ${x+Math.cos(start)*radius} ${y+Math.sin(start)*radius} A ${radius} ${radius} 0 0 ${delta>0?1:0} ${x+Math.cos(start+delta)*radius} ${y+Math.sin(start+delta)*radius}`,x:x+Math.cos(start+delta/2)*(radius+15),y:y+Math.sin(start+delta/2)*(radius+15)}}
const axis=computed(()=>{
 if(props.diagram.kind==='function')return {xmin:props.diagram.domain?.[0]??-5,xmax:props.diagram.domain?.[1]??5,ymin:props.diagram.range?.[0]??-5,ymax:props.diagram.range?.[1]??5}
 if(props.diagram.kind==='scatter'){const xs=values.value.map(v=>v.x??0),ys=values.value.map(v=>v.y??0);let a=Math.min(0,...xs),b=Math.max(0,...xs),c=Math.min(0,...ys),d=Math.max(0,...ys);const xp=Math.max(1,b-a)*.08,yp=Math.max(1,d-c)*.12;return {xmin:a-xp,xmax:b+xp,ymin:c-yp,ymax:d+yp}}
 const ys=values.value.map(v=>v.value??0),min=Math.min(0,...ys),max=Math.max(0,...ys),gap=Math.max(1,max-min)*.15;return {xmin:0,xmax:Math.max(1,ys.length),ymin:min<0?min-gap:0,ymax:max+gap}
})
const sx=(x:number)=>65+(x-axis.value.xmin)/Math.max(.000001,axis.value.xmax-axis.value.xmin)*545
const sy=(y:number)=>345-(y-axis.value.ymin)/Math.max(.000001,axis.value.ymax-axis.value.ymin)*295
const zeroX=computed(()=>sx(Math.max(axis.value.xmin,Math.min(axis.value.xmax,0))))
const zeroY=computed(()=>sy(Math.max(axis.value.ymin,Math.min(axis.value.ymax,0))))
function ticks(min:number,max:number){const raw=(max-min)/6,power=10**Math.floor(Math.log10(Math.max(1e-12,raw))),ratio=raw/power,step=(ratio<=1?1:ratio<=2?2:ratio<=5?5:10)*power;const start=Math.ceil(min/step)*step;return Array.from({length:Math.min(20,Math.max(0,Math.floor((max-start)/step+1e-8)+1))},(_,i)=>+(start+i*step).toPrecision(14))}
const xTicks=computed(()=>ticks(axis.value.xmin,axis.value.xmax)),yTicks=computed(()=>ticks(axis.value.ymin,axis.value.ymax))
const linePoints=computed(()=>values.value.map((v,i)=>`${sx(i+.5)},${sy(v.value??0)}`).join(' '))
const pointString=(segment:number[][])=>segment.map(point=>`${sx(point[0]!)},${sy(point[1]!)}`).join(' ')
const pie=computed(()=>{const total=values.value.reduce((sum,v)=>sum+(v.value??0),0);let at=-Math.PI/2;return values.value.map((v,i)=>{const share=(v.value??0)/Math.max(total,1e-12),start=at;at+=share*2*Math.PI;return {label:v.label,value:v.value??0,share,color:colors[i%colors.length],path:`M 320 205 L ${320+135*Math.cos(start)} ${205+135*Math.sin(start)} A 135 135 0 ${share>.5?1:0} 1 ${320+135*Math.cos(at)} ${205+135*Math.sin(at)} Z`}})})
const connections=computed(()=>{const counts:Record<string,number>={};for(const e of [...(props.diagram.wires??[]),...(props.diagram.components??[])]){counts[e.from]=(counts[e.from]??0)+1;counts[e.to]=(counts[e.to]??0)+1}return counts})
</script>
<template>
 <div class="structured-figure" :data-diagram-kind="diagram.kind">
  <div v-if="diagram.title" class="figure-heading"><MathText :text="diagram.title"/><span v-if="diagram.unit">单位：{{ diagram.unit }}</span></div>
  <table v-if="diagram.kind==='table'" class="figure-table"><thead><tr><th>项目</th><th>数值{{ diagram.unit?`（${diagram.unit}）`:'' }}</th></tr></thead><tbody><tr v-for="v in values" :key="v.label"><td>{{ v.label }}</td><td>{{ v.value }}</td></tr></tbody></table>
  <svg v-else viewBox="0 0 640 420" role="img" :aria-label="diagram.title||`${diagram.kind}题目配图`">
   <title>{{ diagram.title||'题目配图' }}</title>
   <defs><marker :id="marker" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M 0 0 L 7 3.5 L 0 7 Z" fill="#426aee"/></marker></defs>
   <template v-if="diagram.kind==='geometry'">
    <circle v-for="(c,i) in diagram.circles??[]" :key="`c${i}`" :cx="gx(p(c.center).x)" :cy="gy(p(c.center).y)" :r="c.radius*geom.scale" class="geometry-line"/>
    <g v-for="(e,i) in diagram.edges??[]" :key="`e${i}`"><line :x1="gx(p(e.from).x)" :y1="gy(p(e.from).y)" :x2="gx(p(e.to).x)" :y2="gy(p(e.to).y)" class="geometry-line" :stroke-dasharray="e.dashed?'7 5':undefined" :marker-end="e.arrow?`url(#${marker})`:undefined"/><text v-if="e.label" :x="(gx(p(e.from).x)+gx(p(e.to).x))/2+8" :y="(gy(p(e.from).y)+gy(p(e.to).y))/2-8" text-anchor="middle">{{ e.label }}</text></g>
    <g v-for="(mark,i) in diagram.angles??[]" :key="`a${i}`"><path :d="anglePath(mark).d" class="angle-mark"/><text :x="anglePath(mark).x" :y="anglePath(mark).y" text-anchor="middle">{{ mark.label }}</text></g>
    <g v-for="point in diagram.points??[]" :key="point.id"><circle :cx="gx(point.x)" :cy="gy(point.y)" r="3.5" fill="#426aee"/><text :x="gx(point.x)+10" :y="gy(point.y)-9" class="point-label">{{ point.label||point.id }}</text></g>
   </template>
   <template v-else-if="diagram.kind==='circuit'">
    <line v-for="(wire,i) in diagram.wires??[]" :key="i" :x1="gx(p(wire.from).x)" :y1="gy(p(wire.from).y)" :x2="gx(p(wire.to).x)" :y2="gy(p(wire.to).y)" class="circuit-line"/>
    <g v-for="c in diagram.components??[]" :key="c.id">
     <g :transform="component(c).transform" class="circuit-symbol">
      <path :d="`M 0 0 H ${component(c).mid-component(c).width/2} M ${component(c).mid+component(c).width/2} 0 H ${component(c).length}`"/>
      <rect v-if="c.type==='resistor'" :x="component(c).mid-component(c).width/2" y="-8" :width="component(c).width" height="16" rx="2"/>
      <template v-else-if="c.type==='battery'"><path :d="`M ${component(c).mid-component(c).width/2} 0 H ${component(c).mid-5} M ${component(c).mid-5} -17 V 17 M ${component(c).mid+5} -10 V 10 M ${component(c).mid+5} 0 H ${component(c).mid+component(c).width/2}`"/><text :x="component(c).mid-15" y="-20" stroke="none">+</text></template>
      <template v-else-if="c.type==='capacitor'"><path :d="`M ${component(c).mid-component(c).width/2} 0 H ${component(c).mid-5} M ${component(c).mid-5} -15 V 15 M ${component(c).mid+5} -15 V 15 M ${component(c).mid+5} 0 H ${component(c).mid+component(c).width/2}`"/></template>
      <path v-else-if="c.type==='inductor'" :d="coil(c)"/>
      <template v-else-if="c.type==='switch'"><circle :cx="component(c).mid-component(c).width/2" cy="0" r="3"/><circle :cx="component(c).mid+component(c).width/2" cy="0" r="3"/><line :x1="component(c).mid-component(c).width/2" :x2="component(c).mid+component(c).width/2" y1="0" :y2="c.closed?0:-17"/></template>
      <template v-else><path :d="`M ${component(c).mid-component(c).width/2} 0 H ${component(c).mid-12} M ${component(c).mid+12} 0 H ${component(c).mid+component(c).width/2}`"/><circle :cx="component(c).mid" cy="0" r="12"/><path v-if="c.type==='lamp'" :d="`M ${component(c).mid-8} -8 L ${component(c).mid+8} 8 M ${component(c).mid-8} 8 L ${component(c).mid+8} -8`"/><text v-else :x="component(c).mid" y="4" stroke="none" text-anchor="middle" :transform="`rotate(${-component(c).angle},${component(c).mid},0)`">{{ c.type==='ammeter'?'A':'V' }}</text></template>
     </g>
     <text :x="component(c).x" :y="component(c).y" :text-anchor="component(c).anchor">{{ c.id }}{{ c.value!==undefined?` ${format(c.value)} ${c.unit||''}`:'' }}</text>
    </g>
    <circle v-for="node in (diagram.nodes??[]).filter(n=>(connections[n.id]??0)>=3)" :key="node.id" :cx="gx(node.x)" :cy="gy(node.y)" r="4" fill="#334e82"/>
   </template>
   <template v-else-if="diagram.kind==='pie'">
    <template v-for="(slice,i) in pie" :key="i"><circle v-if="slice.share>=.999999999" cx="320" cy="205" r="135" :fill="slice.color"/><path v-else-if="slice.share>0" :d="slice.path" :fill="slice.color" stroke="white" stroke-width="2"/></template>
   </template>
   <template v-else>
    <g v-for="tick in yTicks" :key="`y${tick}`"><line x1="65" x2="610" :y1="sy(tick)" :y2="sy(tick)" class="grid-line"/><text x="55" :y="sy(tick)+4" text-anchor="end">{{ tick }}</text></g>
    <line x1="65" x2="610" :y1="zeroY" :y2="zeroY" class="axis-line"/><line :x1="zeroX" :x2="zeroX" y1="50" y2="345" class="axis-line"/>
    <template v-if="diagram.kind==='function'||diagram.kind==='scatter'">
     <g v-for="tick in xTicks" :key="`x${tick}`"><line :x1="sx(tick)" :x2="sx(tick)" y1="50" y2="345" class="grid-line"/><text :x="sx(tick)" y="369" text-anchor="middle">{{ tick }}</text></g><text x="615" :y="zeroY-8">x</text><text :x="zeroX+8" y="42">y</text>
     <template v-if="diagram.kind==='function'"><g v-for="(curve,i) in diagram.curves??[]" :key="i"><polyline v-for="(segment,j) in curve.segments" :key="j" :points="pointString(segment)" fill="none" :stroke="colors[i%colors.length]" stroke-width="2.5"/><text :x="80+i*155" y="400" :style="{fill:colors[i%colors.length]}">{{ curve.label }}</text></g></template>
     <g v-else v-for="(v,i) in values" :key="i"><circle :cx="sx(v.x??0)" :cy="sy(v.y??0)" r="5" :fill="colors[i%colors.length]"/><text :x="sx(v.x??0)+8" :y="sy(v.y??0)-8">{{ v.label }}</text></g>
    </template>
    <template v-else>
     <polyline v-if="diagram.kind==='line'" :points="linePoints" fill="none" stroke="#426aee" stroke-width="2.5"/>
     <g v-for="(v,i) in values" :key="i"><rect v-if="diagram.kind==='bar'" :x="sx(i+.5)-Math.min(22,180/values.length)" :y="Math.min(sy(v.value??0),zeroY)" :width="Math.min(44,360/values.length)" :height="Math.abs(sy(v.value??0)-zeroY)" rx="3" :fill="(v.value??0)>=0?'#7297f8':'#a48bda'"/><circle v-else :cx="sx(i+.5)" :cy="sy(v.value??0)" r="4" fill="#426aee"/><text :x="sx(i+.5)" :y="sy(v.value??0)+((v.value??0)>=0?-9:17)" text-anchor="middle">{{ format(v.value??0) }}</text><text :x="sx(i+.5)" y="370" text-anchor="middle" :font-size="values.length>8?9:12">{{ v.label }}</text></g>
    </template>
   </template>
  </svg>
  <div v-if="diagram.kind==='pie'" class="pie-legend"><span v-for="(slice,i) in pie" :key="i"><i :style="{background:slice.color}"></i>{{ slice.label }}：{{ format(slice.value) }}</span></div>
  <details v-if="['bar','line','pie','scatter'].includes(diagram.kind)" class="figure-data"><summary>查看图表数据</summary><table class="figure-table"><thead><tr><th>项目</th><th v-if="diagram.kind==='scatter'">x</th><th>{{ diagram.kind==='scatter'?'y':'数值' }}</th></tr></thead><tbody><tr v-for="v in values" :key="v.label"><td>{{ v.label }}</td><td v-if="diagram.kind==='scatter'">{{ v.x }}</td><td>{{ diagram.kind==='scatter'?v.y:v.value }}</td></tr></tbody></table></details>
 </div>
</template>
<style scoped>
.structured-figure{width:100%;min-width:0;background:#fff;border-radius:10px;overflow:hidden}.figure-heading{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;padding:12px 16px;color:#25395f;font-size:14px;font-weight:650}.figure-heading>span{font-size:12px;font-weight:400;color:#6d7f9f}svg{display:block;width:100%;height:auto;min-width:0}text{font:12px system-ui;fill:#425c87}.geometry-line{stroke:#426aee;stroke-width:2;fill:none}.angle-mark{stroke:#ab70cf;stroke-width:1.8;fill:none}.point-label{font-weight:650}.grid-line{stroke:#e9edf6;stroke-width:1}.axis-line{stroke:#7a8eaf;stroke-width:1.4}.circuit-line,.circuit-symbol{stroke:#334e82;stroke-width:2;fill:white}.circuit-symbol path,.circuit-symbol line{fill:none}.circuit-symbol text{fill:#334e82}.figure-table{width:100%;border-collapse:collapse;font-size:13px}.figure-table td,.figure-table th{padding:12px;border:1px solid #e0e7f5;text-align:left}.figure-table th{background:#f3f6ff}
.pie-legend{display:flex;flex-wrap:wrap;gap:10px 20px;padding:0 16px 14px;color:#425c87;font-size:12px}.pie-legend span{display:flex;align-items:center;gap:6px;overflow-wrap:anywhere}.pie-legend i{display:inline-block;width:10px;height:10px;flex:none;border-radius:2px}.figure-data{padding:8px 14px;font-size:12px;color:#62779a}.figure-data summary{cursor:pointer;margin-bottom:8px}
</style>
