package cn.videostudy.api;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.dao.DuplicateKeyException;
import java.util.*;

@Repository
public class OverviewChatStore {
    private final JdbcTemplate jdbc; private final ObjectMapper json;
    public OverviewChatStore(JdbcTemplate jdbc,ObjectMapper json){this.jdbc=jdbc;this.json=json;}
    private Map<String,Object> decode(String value){try{return json.readValue(value,new TypeReference<Map<String,Object>>(){});}catch(Exception e){throw new IllegalStateException(e);}}
    private String encode(Object value){try{return json.writeValueAsString(value);}catch(Exception e){throw new IllegalStateException(e);}}
    public String thread(String course,String context,String client){
        try{jdbc.update("INSERT INTO overview_chat_threads(id,transcription_id,context_key,client_id) VALUES (?,?,?,?)",UUID.randomUUID().toString(),course,context,client);}catch(org.springframework.dao.DataAccessException existing){if(!DatabaseDialect.duplicate(existing))throw existing;}
        return jdbc.queryForObject("SELECT id FROM overview_chat_threads WHERE transcription_id=? AND context_key=? AND client_id=?",String.class,course,context,client);
    }
    public Optional<Map<String,Object>> previous(String thread,String request){return jdbc.query("SELECT user_text,reply_json FROM overview_chat_turns WHERE thread_id=? AND request_id=?",(r,n)->{
        var result=decode(r.getString(2));result.put("message",r.getString(1));return result;},thread,request).stream().findFirst();}
    public List<Map<String,Object>> history(String thread){
        var turns=jdbc.query("SELECT user_text,reply_json FROM overview_chat_turns WHERE thread_id=? ORDER BY created_at,id",(r,n)->Map.of("user",r.getString(1),"answer",decode(r.getString(2))),thread);
        var messages=new ArrayList<Map<String,Object>>();
        for(var turn:turns){messages.add(Map.of("role","user","content",turn.get("user")));var answer=(Map<?,?>)turn.get("answer");
            messages.add(Map.of("role","assistant","content",answer.get("reply"),"citations",answer.get("citations")));}
        return messages;
    }
    public boolean claim(String thread,String token){long now=System.currentTimeMillis();return jdbc.update("UPDATE overview_chat_threads SET lock_token=?,lock_until=? WHERE id=? AND lock_until<?",token,now+300000,thread,now)==1;}
    public int count(String thread){return jdbc.queryForObject("SELECT COUNT(*) FROM overview_chat_turns WHERE thread_id=?",Integer.class,thread);}
    public void save(String thread,String token,String request,String message,Map<String,Object> reply){
        // The claim serializes turns; a stale model response must never append to a recovered thread.
        var tx=new org.springframework.transaction.support.TransactionTemplate(new org.springframework.jdbc.datasource.DataSourceTransactionManager(Objects.requireNonNull(jdbc.getDataSource())));
        tx.executeWithoutResult(status->{
            if(jdbc.update("UPDATE overview_chat_threads SET lock_until=? WHERE id=? AND lock_token=? AND lock_until>?",System.currentTimeMillis()+300000,thread,token,System.currentTimeMillis())!=1)throw new IllegalArgumentException("chat_expired");
            jdbc.update("INSERT INTO overview_chat_turns(id,thread_id,request_id,user_text,reply_json) VALUES (?,?,?,?,?)",UUID.randomUUID().toString(),thread,request,message,encode(reply));
        });
    }
    public void release(String thread,String token){jdbc.update("UPDATE overview_chat_threads SET lock_token=NULL,lock_until=0 WHERE id=? AND lock_token=?",thread,token);}
}
