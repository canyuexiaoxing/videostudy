package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.core.io.ClassPathResource;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class OverviewControllerTest {
    final List<TranscriptionController.TranscriptSegment> segments=List.of(new TranscriptionController.TranscriptSegment("s1",1000,5000,"介绍增长量"));
    Map<String,Object> result(long time){return Map.of("status","completed","headline","增长量课程",
        "summary",List.of(Map.of("text","介绍增长量","citations",List.of(Map.of("sourceId","s1","startMs",time,"endMs",5000,"quote","介绍增长量")))),
        "objectives",List.of(),"keyPoints",List.of(),"pitfalls",List.of(),"highlights",List.of());}
    @Test void validatesOriginalQuotesAndTimes(){
        assertDoesNotThrow(()->OverviewController.validate(result(1000),segments));
        assertThrows(IllegalArgumentException.class,()->OverviewController.validate(result(999),segments));
    }
    @Test void serializedOverviewSurvivesMindMapReplacement()throws Exception{
        var json=new ObjectMapper();
        var source=json.readValue(json.writeValueAsString(Map.of("language","zh","segments",segments,"overview",result(1000))),TranscriptionController.TranscriptResult.class);
        assertEquals("增长量课程",source.overview().get("headline"));
        assertEquals(source.overview(),source.withMindMap(null).overview());
    }
    @Test void cachesAndCascadesWithDeletion()throws Exception{
        var ds=new DriverManagerDataSource("jdbc:h2:mem:"+UUID.randomUUID()+";MODE=MySQL;DB_CLOSE_DELAY=-1","sa","");
        new ResourceDatabasePopulator(new ClassPathResource("db/migration/V1__create_transcription_jobs.sql"),
            new ClassPathResource("db/migration/V3__visual_analysis_mode.sql"),new ClassPathResource("db/migration/V4__coarse_change_percent.sql"),
            new ClassPathResource("db/migration/V7__overview_jobs.sql")).execute(ds);
        var jdbc=new JdbcTemplate(ds);var store=new TranscriptionJobStore(jdbc,new ObjectMapper());var id=UUID.randomUUID().toString();
        store.createQueued(id);store.complete(id,new TranscriptionController.TranscriptResult("zh",segments,List.of(),null,null,null));
        var calls=new java.util.concurrent.atomic.AtomicInteger();
        var agent=new MediaAnalyzer(){
            public TranscriptionController.TranscriptResult analyze(String id,String mode){throw new AssertionError();}
            public Map<String,Object> generateOverview(List<TranscriptionController.TranscriptSegment> s,List<TranscriptionController.PageGroup> p){calls.incrementAndGet();return result(1000);}
        };
        var controller=new OverviewController(jdbc,new ObjectMapper(),store,agent);
        try{
            controller.request(id);
            for(int i=0;i<100&&!jdbc.queryForObject("SELECT status FROM overview_jobs WHERE transcription_id=?",String.class,id).equals("completed");i++)Thread.sleep(10);
            assertEquals("completed",jdbc.queryForObject("SELECT status FROM overview_jobs WHERE transcription_id=?",String.class,id));
            controller.request(id);Thread.sleep(20);assertEquals(1,calls.get());
            store.delete(id);assertEquals(0,jdbc.queryForObject("SELECT COUNT(*) FROM overview_jobs",Integer.class));
        }finally{controller.close();}
    }
}
