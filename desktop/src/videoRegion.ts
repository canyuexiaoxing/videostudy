export type VideoRegion = { x:number; y:number; width:number; height:number }
export type FrameRect = { left:number; top:number; width:number; height:number }
export function normalizeRegion(value:unknown):VideoRegion|null {
 if(!value||typeof value!=='object')return null
 const r=value as VideoRegion
 if(![r.x,r.y,r.width,r.height].every(v=>typeof v==='number'&&Number.isFinite(v))||r.x<0||r.y<0||r.width<=0||r.height<=0||r.x+r.width>1.000001||r.y+r.height>1.000001)return null
 return {x:r.x,y:r.y,width:Math.min(r.width,1-r.x),height:Math.min(r.height,1-r.y)}
}
export function containedFrame(width:number,height:number,videoWidth:number,videoHeight:number):FrameRect {
 if(![width,height,videoWidth,videoHeight].every(v=>Number.isFinite(v)&&v>0))return {left:0,top:0,width:0,height:0}
 const scale=Math.min(width/videoWidth,height/videoHeight),w=Math.min(width,videoWidth*scale),h=Math.min(height,videoHeight*scale)
 return {left:(width-w)/2,top:(height-h)/2,width:w,height:h}
}
export function regionFromPoints(x1:number,y1:number,x2:number,y2:number):VideoRegion|null {
 const clamp=(v:number)=>Math.max(0,Math.min(1,v))
 const a=clamp(x1),b=clamp(y1),c=clamp(x2),d=clamp(y2)
 return normalizeRegion({x:Math.min(a,c),y:Math.min(b,d),width:Math.abs(a-c),height:Math.abs(b-d)})
}
