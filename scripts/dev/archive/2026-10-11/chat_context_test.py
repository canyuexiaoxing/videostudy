from pathlib import Path
p=Path('E:/workp/videostudy/backend-java/src/test/java/cn/videostudy/api/QuestionChatTest.java')
s=p.read_text(encoding='utf-8').replace('    @Test void rejectsAlteredCitations(){','''    @Test void selectsQuestionPagesRatherThanFirstPagesOfWholeSet() throws Exception {
        practice.answer(course,set,session,client,q,0);
        var source=new LinkedHashMap<>(practice.find(set).orElseThrow().source());
        var pages=new ArrayList<Map<String,Object>>();
        for(int i=0;i<7;i++)pages.add(Map.of("pageIndex",i,"content","无关画面","firstFrameTimeMs",10000+i*1000,"lastFrameTimeMs",10999+i*1000));
        pages.add(Map.of("pageIndex",8,"content","分母用基期","firstFrameTimeMs",1000,"lastFrameTimeMs",2000));source.put("pages",pages);
        jdbc.update("UPDATE practice_sets SET source_json=? WHERE id=?",new ObjectMapper().writeValueAsString(source),set);
        var selected=(List<?>)practice.chatContext(course,set,session,client,q).get("pages");
        assertEquals(1,selected.size());assertEquals(8,((Map<?,?>)selected.getFirst()).get("pageIndex"));
        source.put("pages",List.of(Map.of("pageIndex",1,"content","无关画面"),Map.of("pageIndex",2,"content","分母用基期")));
        jdbc.update("UPDATE practice_sets SET source_json=? WHERE id=?",new ObjectMapper().writeValueAsString(source),set);
        selected=(List<?>)practice.chatContext(course,set,session,client,q).get("pages");assertEquals(1,selected.size());assertEquals(2,((Map<?,?>)selected.getFirst()).get("pageIndex"));
    }
    @Test void rejectsAlteredCitations(){''')
p.write_text(s,encoding='utf-8')
