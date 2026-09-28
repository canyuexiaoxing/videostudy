package cn.videostudy.api;

import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class StudyControllerTest {
    @Test
    void createsCourseAndRejectsUnknownJob() throws Exception {
        var mvc = MockMvcBuilders.standaloneSetup(new StudyController("http://127.0.0.1:8000")).build();
        mvc.perform(post("/api/courses").contentType("application/json")
                .content("{\"title\":\"sample.mp4\",\"sizeBytes\":1024}"))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.title").value("sample.mp4"))
            .andExpect(jsonPath("$.id").isNotEmpty());
        mvc.perform(get("/api/jobs/does-not-exist"))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.error").value("job_not_found"));
    }
}
