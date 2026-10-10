package cn.videostudy.api;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.core.io.ClassPathResource;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
class QuestionChatTest {
    JdbcTemplate jdbc; PracticeStore practice; QuestionChatController chat;
    String course=UUID.randomUUID().toString(),client=UUID.randomUUID().toString(),q=UUID.randomUUID().toString(),q2=UUID.randomUUID().toString(),set,session;
    int calls;
    boolean fail;
    @BeforeEach void setup(){
        var ds=new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");
        new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),new ClassPathResource("db/migration/V8__practice.sql"),new ClassPathResource("db/migration/V9__question_chat.sql")).execute(ds);
        jdbc=new JdbcTemplate(ds);var json=new ObjectMapper();practice=new PracticeStore(jdbc,json);
        jdbc.update("INSERT INTO transcription_jobs(id,status) VALUES (?,'completed')",course);
        var source=Map.<String,Object>of("nodes",List.of(Map.of("id","n1","evidenceRefs",List.of(Map.of("sourceId","s1","startMs",1000,"endMs",2000,"quote","分母用基期")))),"pages",List.of());
        var job=practice.request(course,"hash","key","增长率",source,false);set=job.id();
        var question=new LinkedHashMap<String,Object>(Map.of("id",q,"nodeId","n1","prompt","选哪个？","options",List.of("错","对"),"answerIndex",1,"explanation","除以基期","distractorReasons",List.of("误用现期",""),"takeaway","用基期"));
        question.put("citations",((Map<?,?>)((List<?>)source.get("nodes")).getFirst()).get("evidenceRefs"));
        var second=new LinkedHashMap<>(question);second.put("id",q2);
        practice.complete(practice.claim(set).orElseThrow(),Map.of("questions",List.of(question,second)));
        session=practice.createSession(course,set,client);
        var agent=new MediaAnalyzer(){public TranscriptionController.TranscriptResult analyze(String id,String mode){throw new AssertionError();}
            public Map<String,Object> chatQuestion(Map<String,Object> payload){calls++;if(fail)throw new IllegalStateException();
                assertTrue(((Map<?,?>)payload.get("context")).containsKey("feedback"));
                return Map.of("reply","为什么选择现期？","citations",List.of(Map.of("sourceId","s1","startMs",1000,"endMs",2000,"quote","分母用基期")));}};
        chat=new QuestionChatController(new QuestionChatStore(jdbc,json),practice,agent);
    }
    QuestionChatController.Request request(String id){return new QuestionChatController.Request(session,id,"我为什么错？");}
    @Test void restoresIndependentChatsAndIdempotentRequest(){
        practice.answer(course,set,session,client,q,0);practice.answer(course,set,session,client,q2,1);
        String id=UUID.randomUUID().toString();
        var first=chat.send(course,set,q,client,request(id));
        assertEquals(200,first.getStatusCode().value());assertEquals(first.getBody(),chat.send(course,set,q,client,request(id)).getBody());assertEquals(1,calls);
        assertEquals(2,chat.history(course,set,q,client,session).size());assertTrue(chat.history(course,set,q2,client,session).isEmpty());
        assertThrows(IllegalArgumentException.class,()->chat.history(course,set,q,UUID.randomUUID().toString(),session));
        assertThrows(IllegalArgumentException.class,()->chat.history(UUID.randomUUID().toString(),set,q,client,session));
        var fresh=practice.createSession(course,set,client);
        assertEquals(2,chat.history(course,set,q,client,fresh).size());
        jdbc.update("DELETE FROM transcription_jobs WHERE id=?",course);
        assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM question_chat_turns",Integer.class));
    }
    @Test void requiresAnswerAndFailureCanRetry(){
        assertThrows(IllegalArgumentException.class,()->chat.send(course,set,q,client,request(UUID.randomUUID().toString())));
        practice.answer(course,set,session,client,q,0);String id=UUID.randomUUID().toString();fail=true;
        assertEquals(502,chat.send(course,set,q,client,request(id)).getStatusCode().value());
        assertTrue(chat.history(course,set,q,client,session).isEmpty());fail=false;
        assertEquals(200,chat.send(course,set,q,client,request(id)).getStatusCode().value());
    }
    @Test void rejectsConcurrentTurnsAndBoundsCost(){
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
        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post(url).header("X-Practice-Client",client).contentType(org.springframework.http.MediaType.APPLICATION_JSON).content("{}"))
            .andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isBadRequest());
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
            .andRespond(org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess("{\"reply\":\"解释\",\"citations\":[]}",org.springframework.http.MediaType.APPLICATION_JSON));
        assertEquals("解释",new HttpMediaAnalyzer(builder.build()).chatQuestion(Map.of("context",Map.of("question",Map.of("prompt","本题")),"history",List.of(),"message","为什么")).get("reply"));server.verify();
    }
    @Test void selectsQuestionPagesRatherThanFirstPagesOfWholeSet() throws Exception {
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
    @Test void rejectsAlteredCitations(){
        practice.answer(course,set,session,client,q,0);
        var context=practice.chatContext(course,set,session,client,q);
        assertThrows(IllegalArgumentException.class,()->QuestionChatController.validate(Map.of("reply","解释","citations",List.of(Map.of("sourceId","s1","startMs",999,"endMs",2000,"quote","分母用基期"))),context));
    }
}
