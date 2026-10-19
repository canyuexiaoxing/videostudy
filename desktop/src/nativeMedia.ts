export type NativeMedia = {name:string;size:number;fingerprint:string;url:string}
export type SelectedMedia = File | NativeMedia
declare global {interface Window {framewiseMedia?:{register(file:File):Promise<NativeMedia>;restore(fingerprint:string):Promise<NativeMedia|null>}}}
export async function uploadFile(media:SelectedMedia):Promise<File>{
 if(media instanceof File)return media
 const response=await fetch(media.url)
 if(!response.ok)throw new Error('原视频已无法读取，请重新选择文件')
 return new File([await response.blob()],media.name)
}
