from pathlib import Path
p=Path('E:/workp/videostudy')
path=p/'backend-java/src/main/java/cn/videostudy/api/PracticeStore.java'
s=path.read_text(encoding='utf-8')
s=s.replace('context.put("pages",((List<?>)job.source().getOrDefault("pages",List.of())).stream().limit(6).toList());','''var refs=new ArrayList<Map<String,Object>>();evidence.values().forEach(ref->refs.add((Map<String,Object>)ref));
        String text=Objects.toString(q.get("prompt"),"")+Objects.toString(q.get("nodeTitle"),"")+refs.stream().map(ref->Objects.toString(ref.get("quote"),"")).reduce("",String::concat);
        var terms=new HashSet<String>();String normalized=text.toLowerCase().replaceAll("[^\\\\p{L}\\\\p{N}]","");
        for(int i=0;i<normalized.length()-1;i++)terms.add(normalized.substring(i,i+2));
        var pages=(List<Map<String,Object>>)job.source().getOrDefault("pages",List.of());
        context.put("pages",pages.stream().filter(page->{
            if(page.get("firstFrameTimeMs") instanceof Number first && page.get("lastFrameTimeMs") instanceof Number last)
                return refs.stream().anyMatch(ref->((Number)ref.get("startMs")).longValue()<=last.longValue()&&((Number)ref.get("endMs")).longValue()>=first.longValue());
            String content=(Objects.toString(page.get("title"),"")+Objects.toString(page.get("content"),"")+Objects.toString(page.get("ocr"),"")).toLowerCase().replaceAll("[^\\\\p{L}\\\\p{N}]","");
            return terms.stream().anyMatch(content::contains);
        }).limit(6).toList());''')
path.write_text(s,encoding='utf-8')
path=p/'backend-java/src/main/java/cn/videostudy/api/PracticeController.java'
s=path.read_text(encoding='utf-8')
s=s.replace('Map.of("pageIndex",page.pageIndex(),"title",','Map.of("firstFrameTimeMs",page.firstFrameTimeMs(),"lastFrameTimeMs",page.lastFrameTimeMs(),"pageIndex",page.pageIndex(),"title",')
s=s.replace('Map.of("pageIndex",page.pageIndex(),"ocr",','Map.of("firstFrameTimeMs",page.firstFrameTimeMs(),"lastFrameTimeMs",page.lastFrameTimeMs(),"pageIndex",page.pageIndex(),"ocr",')
path.write_text(s,encoding='utf-8')
path=p/'backend-java/src/main/java/cn/videostudy/api/QuestionChatController.java'
s=path.read_text(encoding='utf-8').replace('if(!SubtitleController.validId(id))','if(id==null||!SubtitleController.validId(id))')
path.write_text(s,encoding='utf-8')
path=p/'desktop/src/QuestionChat.vue'
s=path.read_text(encoding='utf-8')
s=s.replace("const requests=latestRequests()", "const requests=latestRequests()\nconst historyReady=ref(false)")
s=s.replace("const ticket=requests.begin();loading.value=true;error.value=''", "const ticket=requests.begin();loading.value=true;historyReady.value=false;error.value=''")
s=s.replace('messages.value=data;await scroll()', 'messages.value=data;historyReady.value=true;await scroll()')
s=s.replace('sending.value||loading.value)return', 'sending.value||loading.value||!historyReady.value)return')
s=s.replace("  messages.value.push({role:'user',content:text},{role:'assistant',content:data.reply,citations:data.citations})", "  const saved=await call('GET',ticket.signal)\n  if(!ticket.current())return\n  messages.value=saved;historyReady.value=true")
s=s.replace('v-if="!messages.length&&!sending"', 'v-if="!sending"')
s=s.replace(':disabled="loading||sending||!draft.trim()"', ':disabled="loading||sending||!historyReady||!draft.trim()"')
path.write_text(s,encoding='utf-8')
path=p/'backend-java/src/test/java/cn/videostudy/api/QuestionChatTest.java'
s=path.read_text(encoding='utf-8').replace('        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get(url).header("X-Practice-Client",client).param("sessionId",session))','''        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post(url).header("X-Practice-Client",client).contentType(org.springframework.http.MediaType.APPLICATION_JSON).content("{}"))
            .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isBadRequest());
        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get(url).header("X-Practice-Client",client).param("sessionId",session))''',1)
path.write_text(s,encoding='utf-8')
