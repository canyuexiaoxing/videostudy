import katex from 'katex'
export type MathPart={text:string;html?:string;display?:boolean;error?:boolean}
export function mathParts(text:string):MathPart[]{
 if(text.length>30000)return [{text}]
 const parts:MathPart[]=[];let plain=0,i=0
 const escaped=(at:number)=>{let count=0;while(at>0&&text[--at]==='\\')count++;return count%2===1}
 while(i<text.length){
  if(text[i]==='`'){const marker=text.startsWith('```',i)?'```':'`';const end=text.indexOf(marker,i+marker.length);i=end<0?text.length:end+marker.length;continue}
  let open='',close='',display=false
  if(!escaped(i)){
   if(text.startsWith('\\\\[',i)){open='\\\\[';close='\\\\]';display=true}
   else if(text.startsWith('\\\\(',i)){open='\\\\(';close='\\\\)'}
   else if(text.startsWith('$$',i)){open=close='$$';display=true}
   else if(text.startsWith('\\[',i)){open='\\[';close='\\]';display=true}
   else if(text.startsWith('\\(',i)){open='\\(';close='\\)'}
   else if(text[i]==='$'){open=close='$'}
  }
  if(!open){i++;continue}
  let end=text.indexOf(close,i+open.length)
  while(end>=0&&(escaped(end)||(close==='$'&&(text[end+1]==='$'||text[end-1]==='$'))))end=text.indexOf(close,end+close.length)
  if(end<0){i+=open.length;continue}
  if(i>plain)parts.push({text:text.slice(plain,i)})
  const source=text.slice(i+open.length,end),original=text.slice(i,end+close.length)
  try{parts.push({text:original,html:katex.renderToString(source,{displayMode:display,throwOnError:true,trust:false,maxExpand:1000,maxSize:20,output:'htmlAndMathml'}),display})}
  catch{parts.push({text:original,error:true})}
  i=end+close.length;plain=i
 }
 if(plain<text.length)parts.push({text:text.slice(plain)})
 return parts
}
