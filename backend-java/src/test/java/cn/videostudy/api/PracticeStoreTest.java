package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.core.io.ClassPathResource;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class PracticeStoreTest {
    JdbcTemplate jdbc; PracticeStore store;
    String course = UUID.randomUUID().toString(), client = UUID.randomUUID().toString();
    String questionId = UUID.randomUUID().toString();
    @BeforeEach void setup() {
        var ds = new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");
        new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),
            new ClassPathResource("db/migration/V8__practice.sql")).execute(ds);
        jdbc = new JdbcTemplate(ds); store = new PracticeStore(jdbc, new ObjectMapper());
        jdbc.update("INSERT INTO transcription_jobs(id,status) VALUES (?,'completed')", course);
    }
    String completed() {
        var set = store.request(course,"hash","key","知识点",Map.of("nodes",List.of()),false);
        var run = store.claim(set.id()).orElseThrow();
        store.complete(run,Map.of("status","completed","questions",List.of(Map.of(
            "id",questionId,"nodeId","n1","title","示例","prompt","请选择","options",List.of("错","对"),
            "answerIndex",1,"explanation","解析","distractorReasons",List.of("错因",""),"takeaway","要点"))));
        return set.id();
    }
    @Test void initialResponseHidesAnswersAndExplanations() throws Exception {
        String set = completed();
        String payload = new ObjectMapper().writeValueAsString(store.publicSet(course,set));
        assertFalse(payload.contains("answerIndex")); assertFalse(payload.contains("explanation"));
        assertFalse(payload.contains("distractorReasons"));
    }
    @Test void clickGradesOnceAndSurvivesReload() {
        String set = completed(), session = store.createSession(course,set,client);
        var first = store.answer(course,set,session,client,questionId,0);
        assertEquals(false,first.get("correct")); assertEquals(1,first.get("answerIndex"));
        assertEquals("错因",first.get("selectedReason"));
        assertEquals(first,store.answer(course,set,session,client,questionId,1));
        assertEquals(1,jdbc.queryForObject("SELECT COUNT(*) FROM practice_answers",Integer.class));
        assertEquals(1,((List<?>)store.session(course,set,session,client).get("feedback")).size());
    }
    @Test void rejectsOtherCourseAndBrowser() {
        String set = completed(), session = store.createSession(course,set,client);
        assertThrows(IllegalArgumentException.class,()->store.publicSet(UUID.randomUUID().toString(),set));
        assertThrows(IllegalArgumentException.class,()->store.session(course,set,session,UUID.randomUUID().toString()));
        assertThrows(IllegalArgumentException.class,()->store.answer(course,set,session,client,questionId,9));
    }
    @Test void reusesCacheAndCascadesAllPracticeData() {
        String set=completed();
        assertEquals(set,store.request(course,"hash","key","知识点",Map.of(),false).id());
        String session=store.createSession(course,set,client);store.answer(course,set,session,client,questionId,1);
        jdbc.update("DELETE FROM transcription_jobs WHERE id=?",course);
        for(String table:List.of("practice_sets","practice_sessions","practice_answers"))
            assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM "+table,Integer.class));
    }
    @Test void temporaryFailureRetriesOnceAndOldRunCannotCompleteNewRun(){
        var set=store.request(course,"hash","retry","知识点",Map.of(),false);
        var first=store.claim(set.id()).orElseThrow();store.fail(first,"temporary",true);
        assertEquals("queued",store.find(set.id()).orElseThrow().status());
        var second=store.claim(set.id()).orElseThrow();
        store.complete(first,Map.of("questions",List.of()));
        assertEquals("processing",store.find(set.id()).orElseThrow().status());
        store.fail(second,"temporary",true);
        assertEquals("failed",store.find(set.id()).orElseThrow().status());
        assertTrue(store.claim(set.id()).isEmpty());
    }
}
