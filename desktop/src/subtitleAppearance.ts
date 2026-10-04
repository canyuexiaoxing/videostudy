export type SubtitleAppearance = {
  vertical:number; fontSize:number; textColor:string; textOpacity:number;
  backgroundColor:string; backgroundOpacity:number; bold:boolean; outline:boolean;
}
export const defaultAppearance:SubtitleAppearance={vertical:80,fontSize:24,textColor:'#ffffff',textOpacity:100,backgroundColor:'#101827',backgroundOpacity:80,bold:false,outline:true}
export function normalizeAppearance(input:unknown):SubtitleAppearance {
  const value=(input&&typeof input==='object'?input:{}) as Partial<SubtitleAppearance>
  const number=(key:keyof SubtitleAppearance,min:number,max:number)=>typeof value[key]==='number'&&Number.isFinite(value[key])?Math.max(min,Math.min(max,value[key] as number)):defaultAppearance[key] as number
  const color=(key:'textColor'|'backgroundColor')=>typeof value[key]==='string'&&/^#[0-9a-f]{6}$/i.test(value[key])?value[key]:defaultAppearance[key]
  return {vertical:number('vertical',5,90),fontSize:number('fontSize',16,48),textColor:color('textColor'),textOpacity:number('textOpacity',0,100),backgroundColor:color('backgroundColor'),backgroundOpacity:number('backgroundOpacity',0,100),bold:typeof value.bold==='boolean'?value.bold:defaultAppearance.bold,outline:typeof value.outline==='boolean'?value.outline:defaultAppearance.outline}
}
function rgba(color:string,opacity:number){return `rgba(${parseInt(color.slice(1,3),16)},${parseInt(color.slice(3,5),16)},${parseInt(color.slice(5,7),16)},${opacity/100})`}
export function appearanceCss(settings:SubtitleAppearance){
  const s=normalizeAppearance(settings)
  return `.study-app .player-panel video::cue {color:${rgba(s.textColor,s.textOpacity)};background-color:${rgba(s.backgroundColor,s.backgroundOpacity)};font-size:${s.fontSize}px;font-weight:${s.bold?700:400};font-family:"Microsoft YaHei",sans-serif;text-shadow:${s.outline?'0 1px 2px #000,1px 0 2px #000,-1px 0 2px #000':'none'};}`
}
export function positionCue(cue:{line?:number|string;snapToLines?:boolean;lineAlign?:string;position?:number|string;size?:number;align?:string},settings:SubtitleAppearance){
  cue.snapToLines=false;cue.line=normalizeAppearance(settings).vertical;cue.lineAlign='center';cue.position=50;cue.size=90;cue.align='center'
}
