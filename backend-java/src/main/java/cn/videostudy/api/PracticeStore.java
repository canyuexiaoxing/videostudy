package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.dao.DuplicateKeyException;
import java.util.*;

@Repository
public class PracticeStore {
    private final JdbcTemplate jdbc;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    public record SetJob(String id,String analysisId,String sourceHash,String title,String status,
                         Map<String,Object> source,Map<String,Object> result,String error) {}
    public record Run(String id,String token,Map<String,Object> source) {}
    public PracticeStore(JdbcTemplate jdbc,ObjectMapper json) {
        this.jdbc=jdbc;this.json=json;
        tx=new TransactionTemplate(new DataSourceTransactionManager(Objects.requireNonNull(jdbc.getDataSource())));
    }
    private String encode(Object data) {
        try{return json.writeValueAsString(data);}catch(Exception error){throw new IllegalStateException(error);}
    }
    private Map<String,Object> decode(String data) {
        if(data==null)return null;
        try{return json.readValue(data,new TypeReference<Map<String,Object>>(){});}catch(Exception error){throw new IllegalStateException(error);}
    }
    public SetJob request(String analysis,String hash,String key,String title,Map<String,Object> source,boolean retry) {
        try{jdbc.update("INSERT INTO practice_sets(id,transcription_id,source_hash,request_key,scope_title,status,source_json) VALUES (?,?,?,?,?,'queued',?)",
            UUID.randomUUID().toString(),analysis,hash,key,title,encode(source));}
        catch(DuplicateKeyException existing){/* Same evidence and settings reuse a saved set. */}
        if(retry)jdbc.update("UPDATE practice_sets SET status='queued',attempt_count=0,error_code=NULL WHERE transcription_id=? AND request_key=? AND status='failed'",analysis,key);
        String id=jdbc.queryForObject("SELECT id FROM practice_sets WHERE transcription_id=? AND request_key=?",String.class,analysis,key);
        return find(id).orElseThrow();
    }
    public Optional<SetJob> find(String id) {
        return jdbc.query("SELECT * FROM practice_sets WHERE id=?",(r,n)->new SetJob(r.getString("id"),r.getString("transcription_id"),
            r.getString("source_hash"),r.getString("scope_title"),r.getString("status"),decode(r.getString("source_json")),
            decode(r.getString("result_json")),r.getString("error_code")),id).stream().findFirst();
    }
    public List<String> due(){return jdbc.query("SELECT id FROM practice_sets WHERE status='queued' AND attempt_count<2 ORDER BY created_at LIMIT 5",(r,n)->r.getString(1));}
    public Optional<Run> claim(String id) {
        String token=UUID.randomUUID().toString();
        if(jdbc.update("UPDATE practice_sets SET status='processing',attempt_count=attempt_count+1,run_token=? WHERE id=? AND status='queued' AND attempt_count<2",token,id)!=1)return Optional.empty();
        return find(id).map(set->new Run(id,token,set.source()));
    }
    public void complete(Run run,Map<String,Object> result) {
        jdbc.update("UPDATE practice_sets SET status='completed',result_json=?,error_code=NULL,run_token=NULL WHERE id=? AND run_token=? AND status='processing'",encode(result),run.id(),run.token());
    }
    public void fail(Run run,String code,boolean temporary) {
        jdbc.update("UPDATE practice_sets SET status=CASE WHEN ? AND attempt_count<2 THEN 'queued' ELSE 'failed' END,error_code=?,run_token=NULL WHERE id=? AND run_token=?",temporary,code,run.id(),run.token());
    }
    public void recover(){jdbc.update("UPDATE practice_sets SET status=CASE WHEN attempt_count<2 THEN 'queued' ELSE 'failed' END,run_token=NULL,error_code='practice_interrupted' WHERE status='processing'");}
    private SetJob owned(String analysis,String id) {
        var set=find(id).orElseThrow(()->new IllegalArgumentException("practice_not_found"));
        if(!set.analysisId().equals(analysis))throw new IllegalArgumentException("practice_not_found");
        return set;
    }
    @SuppressWarnings("unchecked") private List<Map<String,Object>> questions(SetJob set) {
        return set.result()==null?List.of():(List<Map<String,Object>>)set.result().getOrDefault("questions",List.of());
    }
    public Map<String,Object> publicSet(String analysis,String id) {
        var set=owned(analysis,id);var result=new LinkedHashMap<String,Object>();
        result.put("id",id);result.put("analysisId",analysis);result.put("sourceHash",set.sourceHash());result.put("title",set.title());
        result.put("status",set.status());result.put("error",set.error());
        result.put("count",set.source().get("count"));result.put("difficulty",set.source().get("difficulty"));
        if(set.result()!=null)for(String key:List.of("rejectedCount","requestedCount","modelId","promptVersion"))result.put(key,set.result().get(key));
        result.put("questions",questions(set).stream().map(q->{
            var publicQuestion=new LinkedHashMap<String,Object>();
            for(String key:List.of("id","nodeId","nodeTitle","kind","title","prompt","options","diagram","scenario","validation"))
                if(q.containsKey(key))publicQuestion.put(key,q.get(key));
            return publicQuestion;
        }).toList());
        return result;
    }
    public List<Map<String,Object>> list(String analysis) {
        return jdbc.query("SELECT id FROM practice_sets WHERE transcription_id=? ORDER BY created_at DESC",(r,n)->r.getString(1),analysis)
            .stream().map(id->{var set=publicSet(analysis,id);set.remove("questions");return set;}).toList();
    }
    public String createSession(String analysis,String setId,String client) {
        var set=owned(analysis,setId);
        if(!"completed".equals(set.status())||questions(set).isEmpty())throw new IllegalArgumentException("practice_not_ready");
        String id=UUID.randomUUID().toString();
        jdbc.update("INSERT INTO practice_sessions(id,set_id,client_id) VALUES (?,?,?)",id,setId,client);return id;
    }
    public Optional<String> latestSession(String set,String client){return jdbc.query("SELECT id FROM practice_sessions WHERE set_id=? AND client_id=? ORDER BY created_at DESC LIMIT 1",(r,n)->r.getString(1),set,client).stream().findFirst();}
    private void requireSession(String analysis,String set,String session,String client) {
        owned(analysis,set);
        if(jdbc.queryForObject("SELECT COUNT(*) FROM practice_sessions WHERE id=? AND set_id=? AND client_id=?",Integer.class,session,set,client)!=1)
            throw new IllegalArgumentException("practice_session_not_found");
    }
    private Map<String,Object> feedback(Map<String,Object> q,int chosen) {
        int answer=((Number)q.get("answerIndex")).intValue();
        var f=new LinkedHashMap<String,Object>();f.put("questionId",q.get("id"));f.put("selectedIndex",chosen);f.put("answerIndex",answer);
        f.put("correct",chosen==answer);f.put("explanation",q.get("explanation"));f.put("takeaway",q.get("takeaway"));
        f.put("citations",q.getOrDefault("citations",List.of()));
        f.put("selectedReason",chosen==answer?"":((List<?>)q.get("distractorReasons")).get(chosen));return f;
    }
    public Map<String,Object> answer(String analysis,String setId,String session,String client,String questionId,int chosen) {
        return tx.execute(status->{
            requireSession(analysis,setId,session,client);
            var q=questions(owned(analysis,setId)).stream().filter(item->questionId.equals(item.get("id"))).findFirst()
                .orElseThrow(()->new IllegalArgumentException("question_not_found"));
            if(chosen<0||chosen>=((List<?>)q.get("options")).size())throw new IllegalArgumentException("invalid_option");
            try{jdbc.update("INSERT INTO practice_answers(session_id,question_id,selected_index,correct) VALUES (?,?,?,?)",session,questionId,chosen,chosen==((Number)q.get("answerIndex")).intValue());}
            catch(DuplicateKeyException existing){/* First answer wins, including concurrent requests. */}
            int recorded=jdbc.queryForObject("SELECT selected_index FROM practice_answers WHERE session_id=? AND question_id=?",Integer.class,session,questionId);
            return feedback(q,recorded);
        });
    }
    public void requireChatSession(String analysis,String set,String session,String client,String questionId) {
        requireSession(analysis,set,session,client);
        if(questions(owned(analysis,set)).stream().noneMatch(q->questionId.equals(q.get("id"))))
            throw new IllegalArgumentException("question_not_found");
    }
    @SuppressWarnings("unchecked") public Map<String,Object> chatContext(String analysis,String set,String session,String client,String questionId) {
        requireChatSession(analysis,set,session,client,questionId);
        var job=owned(analysis,set);
        var q=questions(job).stream().filter(item->questionId.equals(item.get("id"))).findFirst().orElseThrow();
        var answers=jdbc.query("SELECT selected_index FROM practice_answers WHERE session_id=? AND question_id=?",(r,n)->r.getInt(1),session,questionId);
        if(answers.isEmpty())throw new IllegalArgumentException("answer_required");
        var evidence=new LinkedHashMap<String,Object>();
        for(var node:(List<Map<String,Object>>)job.source().getOrDefault("nodes",List.of())) {
            if(!Objects.equals(q.get("nodeId"),node.get("id")))continue;
            for(var ref:(List<Map<String,Object>>)node.getOrDefault("evidenceRefs",List.of()))evidence.put((String)ref.get("sourceId"),ref);
        }
        var context=new LinkedHashMap<String,Object>();
        context.put("question",q);context.put("feedback",feedback(q,answers.getFirst()));
        context.put("evidence",new ArrayList<>(evidence.values()));
        var refs=new ArrayList<Map<String,Object>>();evidence.values().forEach(ref->refs.add((Map<String,Object>)ref));
        String text=Objects.toString(q.get("prompt"),"")+Objects.toString(q.get("nodeTitle"),"")+refs.stream().map(ref->Objects.toString(ref.get("quote"),"")).reduce("",String::concat);
        var terms=new HashSet<String>();String normalized=text.toLowerCase().replaceAll("[^\\p{L}\\p{N}]","");
        for(int i=0;i<normalized.length()-1;i++)terms.add(normalized.substring(i,i+2));
        var pages=(List<Map<String,Object>>)job.source().getOrDefault("pages",List.of());
        context.put("pages",pages.stream().filter(page->{
            if(page.get("firstFrameTimeMs") instanceof Number first && page.get("lastFrameTimeMs") instanceof Number last)
                return refs.stream().anyMatch(ref->((Number)ref.get("startMs")).longValue()<=last.longValue()&&((Number)ref.get("endMs")).longValue()>=first.longValue());
            String content=(Objects.toString(page.get("title"),"")+Objects.toString(page.get("content"),"")+Objects.toString(page.get("ocr"),"")).toLowerCase().replaceAll("[^\\p{L}\\p{N}]","");
            return terms.stream().anyMatch(content::contains);
        }).limit(6).toList());
        return context;
    }
    public Map<String,Object> session(String analysis,String setId,String session,String client) {
        requireSession(analysis,setId,session,client);
        var set=owned(analysis,setId);var byId=new HashMap<String,Map<String,Object>>();questions(set).forEach(q->byId.put((String)q.get("id"),q));
        var answers=jdbc.query("SELECT question_id,selected_index FROM practice_answers WHERE session_id=? ORDER BY created_at",(r,n)->feedback(byId.get(r.getString(1)),r.getInt(2)),session);
        return Map.of("id",session,"setId",setId,"feedback",answers);
    }
}
