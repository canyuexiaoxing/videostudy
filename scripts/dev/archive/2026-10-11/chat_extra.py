from pathlib import Path
p=Path('E:/workp/videostudy')
path=p/'backend-java/src/test/java/cn/videostudy/api/QuestionChatTest.java'
text=path.read_text(encoding='utf-8')
text=text.replace('    @Test void rejectsAlteredCitations(){', '''    @Test void rejectsConcurrentTurnsAndBoundsCost(){
        practice.answer(course,set,session,client,q,0);
        var store=new QuestionChatStore(jdbc,new ObjectMapper());String thread=store.thread(set,q,client),token=UUID.randomUUID().toString();
        assertTrue(store.claim(thread,token));assertFalse(store.claim(thread,UUID.randomUUID().toString()));
        assertEquals(409,chat.send(course,set,q,client,request(UUID.randomUUID().toString())).getStatusCode().value());assertEquals(0,calls);
        jdbc.update("UPDATE question_chat_threads SET lock_until=1 WHERE id=?",thread);
        String recovered=UUID.randomUUID().toString();assertTrue(store.claim(thread,recovered));
        assertThrows(IllegalArgumentException.class,()->store.save(thread,token,UUID.randomUUID().toString(),"stale",Map.of("reply","old","citations",List.of())));
        store.release(thread,recovered);
        for(int i=0;i<20;i++)assertEquals(200,chat.send(course,set,q,client,request(UUID.randomUUID().toString())).getStatusCode().value());
        assertEquals(429,chat.send(course,set,q,client,request(UUID.randomUUID().toString())).getStatusCode().value());assertEquals(20,calls);
    }
    @Test void httpEndpointCarriesContextWithoutClientSuppliedEvidence() throws Exception {
        practice.answer(course,set,session,client,q,0);
        var mvc=org.springframework.test.web.servlet.setup.MockMvcBuilders.standaloneSetup(chat).build();
        String url="/api/transcriptions/"+course+"/practice/"+set+"/questions/"+q+"/chat";
        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post(url).header("X-Practice-Client",client)
            .contentType(org.springframework.http.MediaType.APPLICATION_JSON).content(new ObjectMapper().writeValueAsString(request(UUID.randomUUID().toString()))))
            .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isOk())
            .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$.citations[0].startMs").value(1000));
        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get(url).header("X-Practice-Client",client).param("sessionId",session))
            .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath("$[1].content").value("为什么选择现期？"));
        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get(url).header("X-Practice-Client",UUID.randomUUID().toString()).param("sessionId",session))
            .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isBadRequest());
    }
    @Test void javaPythonTransportUsesQuestionChatEndpoint(){
        var builder=org.springframework.web.client.RestClient.builder().baseUrl("http://agent");
        var server=org.springframework.test.web.client.MockRestServiceServer.bindTo(builder).build();
        server.expect(org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo("http://agent/question-chat"))
            .andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath("$.message").value("为什么"))
            .andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath("$.context.question.prompt").value("本题"))
            .andRespond(org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess("{\\"reply\\":\\"解释\\",\\"citations\\":[]}",org.springframework.http.MediaType.APPLICATION_JSON));
        assertEquals("解释",new HttpMediaAnalyzer(builder.build()).chatQuestion(Map.of("context",Map.of("question",Map.of("prompt","本题")),"history",List.of(),"message","为什么")).get("reply"));server.verify();
    }
    @Test void rejectsAlteredCitations(){''')
path.write_text(text,encoding='utf-8')
path=p/'agent-python/test_question_chat.py'
text=path.read_text(encoding='utf-8')
text+='''
    def test_fastapi_route_uses_saved_context(self):
        from app import app
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        with patch('question_chat.ask_provider',return_value={'reply':'解释','sourceIds':['s1']}) as provider:
            response=TestClient(app).post('/question-chat',json={'context':self.context(),'history':[],'message':'为什么'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['citations'],self.context()['evidence'])
        self.assertEqual(provider.call_count,1)
'''
path.write_text(text,encoding='utf-8')
path=p/'README.md'
text=path.read_text(encoding='utf-8')
text+='''
## 本题答疑

真实课程题目作答后，点击题目下方“本题答疑 · 解释我的思路”。每道题按题库与匿名浏览器标识单独保存对话，再次打开恢复；重做同题保留之前交流。打开与恢复不调用 AI，发送才调用现有 DeepSeek 服务。

服务器自动带入题目、当前答案、知识点和生成时保存的相关课程证据/页面分析，不重新上传或分析视频。模型引用只允许来自已有证据，回看沿用原视频指纹校验。错误选项解释只是可能原因，回答不应被当作已确认的个人诊断。第一版未提供全课程检索、自动掌握状态评定或知识点聊天。

输入上限 2000 字，每题每浏览器最多 20 次成功交流；模型使用最近 12 条消息和保存的上下文。失败保留输入，重复请求复用成功结果；删除课程解析级联清理题目对话。清除浏览器标识后不能恢复原匿名对话，不提供账户级隔离保证。

需要重启更新后的 Python/Java 服务；Java 启动时 Flyway 自动应用 `V9__question_chat.sql`。前端沿用本地开发 API 地址。
'''
path.write_text(text,encoding='utf-8')
