from pathlib import Path
root=Path(r'E:\workp\videostudy')
def edit(file,old,new):
 p=root/file;s=p.read_text(encoding='utf-8');assert s.count(old)==1,(file,old);p.write_text(s.replace(old,new),encoding='utf-8')
edit('desktop/src/App.vue',"const existingJobId = ref(localStorage.getItem('lastAnalysisId') ?? '')","const existingJobId = ref('')")
edit('desktop/src/App.vue',':course-id="existingJobId || undefined"',':course-id="(transcript.length || pageGroups.length || mindMap) && existingJobId ? existingJobId : undefined"')
edit('desktop/src/AiPractice.vue',"const demo=computed(()=>!props.courseId&&!props.hasMedia)","const showDemo=ref(false)\nconst demo=computed(()=>showDemo.value&&!props.courseId&&!props.hasMedia)\nwatch(()=>props.hasMedia,()=>{showDemo.value=false})")
edit('desktop/src/AiPractice.vue',"scope.value='';session.value='';if(props.courseId)","scope.value='';session.value='';showDemo.value=false;if(props.courseId)")
edit('desktop/src/AiPractice.vue',"{{ demo?'静态演示':'知识点练习' }}","{{ demo?'静态演示':courseId?'知识点练习':'未选择课程' }}")
edit('desktop/src/AiPractice.vue','  <div v-if="!demo" class="practice-settings">','''  <button v-if="!courseId&&!hasMedia" type="button" class="practice-secondary" @click="showDemo=!showDemo;feedback={};index=0">{{ demo?'关闭示例题':'查看示例题' }}</button>
  <div v-if="courseId&&!demo" class="practice-settings">''')
edit('desktop/src/AiPractice.vue',"{{ active?.status==='completed'?","{{ !courseId&&!hasMedia?'请先选择并分析视频，或从历史记录打开课程，随后显示对应练习。':active?.status==='completed'?")
p=root/'docs/superpowers/specs/2026-10-10-practice-startup.md';p.write_text('''# 启动时练习状态隔离
用户反馈未打开历史时残留上次AI题目。根因是启动将lastAnalysisId作为当前课程，练习组件自动恢复其题库；另有未选课时自动显示固定示例题。
启动保持当前分析编号为空，保留历史数据；只有已加载课程材料时将课程编号传入练习组件，输入编号不触发练习读取。示例题改为手动打开，选择媒体或课程时退出演示。
浏览器回归覆盖带旧localStorage的启动、未加载时输入编号、主动打开历史恢复题库、再次刷新为空；使用模拟API，不调用AI、不删除历史。
''',encoding='utf-8')
