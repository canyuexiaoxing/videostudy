export type NoteTool='pen'|'highlight'|'arrow'|'rectangle'|'ellipse'|'eraser'
export type NotePoint={x:number;y:number}
export type NoteStroke={tool:NoteTool;color:string;size:number;dashed:boolean;points:NotePoint[]}
export type NoteAnnotation={base:Blob;strokes:NoteStroke[]}
export function drawNoteStroke(ctx:CanvasRenderingContext2D,stroke:NoteStroke){
 const first=stroke.points[0],last=stroke.points.at(-1);if(!first||!last)return
 ctx.save();ctx.globalCompositeOperation=stroke.tool==='eraser'?'destination-out':'source-over'
 ctx.globalAlpha=stroke.tool==='highlight'?.28:1;ctx.strokeStyle=stroke.color;ctx.fillStyle=stroke.color
 ctx.lineWidth=stroke.size*(stroke.tool==='highlight'?3:stroke.tool==='eraser'?3:1);ctx.lineCap='round';ctx.lineJoin='round';ctx.setLineDash(stroke.dashed&&stroke.tool!=='eraser'?[stroke.size*3,stroke.size*2]:[]);ctx.beginPath()
 if(stroke.tool==='rectangle')ctx.rect(first.x,first.y,last.x-first.x,last.y-first.y)
 else if(stroke.tool==='ellipse')ctx.ellipse((first.x+last.x)/2,(first.y+last.y)/2,Math.abs(last.x-first.x)/2,Math.abs(last.y-first.y)/2,0,0,Math.PI*2)
 else if(stroke.tool==='arrow'){
  const angle=Math.atan2(last.y-first.y,last.x-first.x),head=Math.max(14,stroke.size*4)
  ctx.moveTo(first.x,first.y);ctx.lineTo(last.x,last.y);ctx.stroke();ctx.setLineDash([]);ctx.beginPath()
  ctx.moveTo(last.x-head*Math.cos(angle-.5),last.y-head*Math.sin(angle-.5));ctx.lineTo(last.x,last.y);ctx.lineTo(last.x-head*Math.cos(angle+.5),last.y-head*Math.sin(angle+.5))
 }else{ctx.moveTo(first.x,first.y);for(const point of stroke.points.slice(1))ctx.lineTo(point.x,point.y);if(stroke.points.length===1)ctx.lineTo(first.x+.01,first.y)}
 ctx.stroke();ctx.restore()
}
