from pathlib import Path
p=Path('E:/workp/videostudy')
def write(name, text):
    target=p/name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')
write('docs/superpowers/specs/2026-10-10-question-chat.md', '''# 本题答疑
用户已确认新增每道题独立对话，恢复原记录，复用已保存的视频分析；先验证现有链路再开发。
答题后显示本题答疑，可询问解法或解释自己的选择。课程、题库、题目、匿名浏览器标识共同隔离记录；重做同题保留聊天，当前答案来自当前答题会话。
Java 从服务器保存的题目及生成时课程证据快照组装上下文，不相信客户端传入的答案、引用、时间。Python 使用现有 DeepSeek 配置，一次提问一次调用，最近 12 条消息；正文仅纯文本显示。错误选项解释不当作已确认个人错因；信息不足应澄清。课程证据是数据，不是指令。
模型返回 reply、sourceIds，引用从快照重建，无未知 ID、无模型时间。引用存在不保证语义成立；界面提醒人工判断。已保存相关页面理解作为补充，不重新上传或转写视频。第一版不实现全课程检索或掌握状态判定。
每条输入最多 2000 字，每题每浏览器最多 20 次成功交流；请求 UUID 幂等，失败保留草稿，忙碌拒绝并行请求；锁有超时恢复。删除解析级联删除答疑。打开、恢复不调用 AI。
验证：现有回归；Python 虚构引用/输入边界；Java H2+接口测试隔离、持久化、幂等、失败恢复、级联；前端切题竞态测试、构建和模拟 API 浏览器检查。不自动调用付费模型或重跑真实课程。
''')
write('docs/superpowers/plans/2026-10-10-question-chat.md', '''# 本题答疑实施计划
目标：保持已有分析/练习/回看链路，在现有练习加入每题独立且可恢复的答疑。
规格：../specs/2026-10-10-question-chat.md
- [x] 验证现有链路：前端31、Java65、Python157（跳过1）、构建通过。
- [ ] 先写 Python 和 Java 测试，确认功能缺失导致失败。
- [ ] Python grounded chat：复用配置、限制输入与历史、重建引用。
- [ ] Java V9 持久化与答题会话校验、幂等、并发租约、错误处理。
- [ ] Vue 本题答疑组件及过期响应保护、引用回看。
- [ ] 回归、构建、浏览器模拟接口检查；补充验证文档。
''')
write('agent-python/test_question_chat.py', '''import unittest
from question_chat import reply_to_question

class ChatTests(unittest.TestCase):
    def context(self):
        return {'question': {'prompt': '增长率？'}, 'feedback': {'selectedReason': '误用现期'},
                'evidence': [{'sourceId': 's1', 'startMs': 1000, 'endMs': 2000, 'quote': '分母是基期'}], 'pages': []}
    def test_rebuilds_citations_and_keeps_question_history(self):
        seen=[]
        def ask(payload):
            seen.append(payload)
            return {'reply': '你为什么用现期？', 'sourceIds': ['s1', 's1'], 'startMs': 99999}
        result=reply_to_question(self.context(), [{'role':'user','content':'上次问题'}], '我除以现期', ask)
        self.assertEqual(result['citations'], self.context()['evidence'])
        self.assertEqual(seen[0]['message'], '我除以现期')
        self.assertEqual(len(seen[0]['history']), 1)
    def test_rejects_invented_sources(self):
        with self.assertRaises(ValueError):
            reply_to_question(self.context(), [], '为什么', lambda p: {'reply':'解释','sourceIds':['fake']})
    def test_allows_clarification_without_claiming_evidence(self):
        self.assertEqual(reply_to_question(self.context(), [], '我猜的', lambda p: {'reply':'请说说思路','sourceIds':[]})['citations'], [])
    def test_bounds_message_and_history_before_provider(self):
        with self.assertRaises(ValueError): reply_to_question(self.context(), [], 'x'*2001, lambda p: self.fail())
        captured=[]
        reply_to_question(self.context(), [{'role':'user','content':str(i)} for i in range(30)], '为什么', lambda p: captured.append(p) or {'reply':'解释','sourceIds':[]})
        self.assertEqual(len(captured[0]['history']),12)
        with self.assertRaises(ValueError): reply_to_question(self.context(), [], '为什么', lambda p: {'reply':'','sourceIds':[]})
''')
write('backend-java/src/test/java/cn/videostudy/api/QuestionChatTest.java', '''package cn.videostudy.api;
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
    @Test void rejectsAlteredCitations(){
        var context=practice.chatContext(course,set,session,client,q); // unanswered must be rejected
    }
}
'''.replace('var context=practice.chatContext(course,set,session,client,q); // unanswered must be rejected', '''practice.answer(course,set,session,client,q,0);
        var context=practice.chatContext(course,set,session,client,q);
        assertThrows(IllegalArgumentException.class,()->QuestionChatController.validate(Map.of("reply","解释","citations",List.of(Map.of("sourceId","s1","startMs",999,"endMs",2000,"quote","分母用基期"))),context));'''))
