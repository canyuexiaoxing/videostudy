from pathlib import Path
p=Path('E:/workp/videostudy/desktop/src/AiOverview.vue')
s=p.read_text(encoding='utf-8')
s=s.replace("import { onUnmounted, ref, watch } from 'vue'", "import { computed, onUnmounted, ref, watch } from 'vue'")
s=s.replace("const emit=defineEmits<{seek:[timeMs:number,sourceId:string]}>()\n",'')
start=s.index('const sections=')
end=s.index('watch(()=>',start)
s=s[:start]+'''const analysis=computed(()=>{
  const parts=[...new Set((result.value?.summary??[]).map(item=>item.text.trim()).filter(Boolean))]
  return parts.map(text=>/[。！？.!?]$/.test(text)?text:`${text}。`).join('')
})
let controller:AbortController|undefined
'''+s[end:]
start=s.index('  <div class="overview-heading">')
end=s.index('  <div v-else',start)
s=s[:start]+'''  <div v-if="result?.status==='completed'" class="overview-content">
    <p class="overview-analysis">{{ analysis }}</p>
  </div>
'''+s[end:]
s=s.replace('概括课程内容，并提供回看依据。','概括课程内容。')
s+='''
<style scoped>
.overview-analysis{margin:0;padding:4px 0;font-size:14px;line-height:1.9;color:#405779;overflow-wrap:anywhere}
</style>
'''
p.write_text(s,encoding='utf-8')
p=Path('E:/workp/videostudy/desktop/src/App.vue')
s=p.read_text(encoding='utf-8').replace('课程概括与重点回看','课程整体分析').replace('<AiOverview :course-id="existingJobId" :ready="!!transcript.length" @seek="seekTo" />','<AiOverview :course-id="existingJobId" :ready="!!transcript.length" />')
p.write_text(s,encoding='utf-8')
