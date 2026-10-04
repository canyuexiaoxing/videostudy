package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.core.io.ClassPathResource;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ChapterControllerTest {
    private final List<TranscriptionController.TranscriptSegment> segments=List.of(
        new TranscriptionController.TranscriptSegment("s1",1000,5000,"介绍"),
        new TranscriptionController.TranscriptSegment("s2",12000,20000,"例题"));
    Map<String,Object> result(long secondStart) {return Map.of("status","completed","chapters",List.of(
        Map.of("id","c1","title","介绍","sourceSegmentId","s1","startMs",0,"endMs",secondStart),
        Map.of("id","c2","title","例题","sourceSegmentId","s2","startMs",secondStart,"endMs",20000)));}
    @Test void rejectsInventedTimesAndAcceptsContiguousGroundedChapters() {
        assertDoesNotThrow(()->ChapterController.validate(result(12000),segments));
        assertThrows(IllegalArgumentException.class,()->ChapterController.validate(result(11000),segments));
    }
    @Test void generatedChaptersAreCachedAndDeletedWithCourse() throws Exception {
        var ds=new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");
        new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),
            new ClassPathResource("db/migration/V3__visual_analysis_mode.sql"),new ClassPathResource("db/migration/V4__coarse_change_percent.sql"),
            new ClassPathResource("db/migration/V6__chapter_jobs.sql")).execute(ds);
        var jdbc=new JdbcTemplate(ds);var json=new ObjectMapper();var store=new TranscriptionJobStore(jdbc,json);
        var id=UUID.randomUUID().toString();store.createQueued(id);
        store.complete(id,new TranscriptionController.TranscriptResult("zh",segments,List.of(),null,null,null));
        var calls=new java.util.concurrent.atomic.AtomicInteger();
        var analyzer=new MediaAnalyzer(){
            public TranscriptionController.TranscriptResult analyze(String id,String mode){throw new AssertionError();}
            public Map<String,Object> generateChapters(List<TranscriptionController.TranscriptSegment> s,List<TranscriptionController.PageGroup> p){calls.incrementAndGet();return result(12000);}
        };
        var controller=new ChapterController(jdbc,json,store,analyzer);
        try {
            controller.request(id);
            for(int i=0;i<100&&!jdbc.queryForObject("SELECT status FROM chapter_jobs WHERE transcription_id=?",String.class,id).equals("completed");i++)Thread.sleep(10);
            assertEquals("completed",jdbc.queryForObject("SELECT status FROM chapter_jobs WHERE transcription_id=?",String.class,id));
            controller.request(id);Thread.sleep(20);assertEquals(1,calls.get());
            store.delete(id);assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM chapter_jobs",Integer.class));
        }finally{controller.close();}
    }
}
