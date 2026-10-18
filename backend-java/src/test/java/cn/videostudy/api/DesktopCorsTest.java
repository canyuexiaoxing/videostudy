package cn.videostudy.api;
import org.junit.jupiter.api.Test;import org.springframework.web.bind.annotation.*;import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;import org.springframework.mock.web.MockServletContext;import org.springframework.test.web.servlet.setup.MockMvcBuilders;import org.springframework.web.servlet.config.annotation.EnableWebMvc;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
class DesktopCorsTest {
 @RestController public static class Endpoint{@GetMapping("/api/test-desktop") @CrossOrigin(origins={"http://127.0.0.1:5173"}) public String get(){return "ok";}}
 @org.springframework.context.annotation.Configuration @EnableWebMvc public static class Web{}
 @Test void packagedOriginWorksWithoutGrantingUnrelatedWebsites()throws Exception{
  try(var context=new AnnotationConfigWebApplicationContext()){
   context.setServletContext(new MockServletContext());context.register(Web.class,Endpoint.class,DesktopCors.class);context.refresh();var mvc=MockMvcBuilders.webAppContextSetup(context).build();
   mvc.perform(get("/api/test-desktop").header("Origin","app://framewise")).andExpect(status().isOk()).andExpect(header().string("Access-Control-Allow-Origin","app://framewise"));
   mvc.perform(options("/api/test-desktop").header("Origin","app://framewise").header("Access-Control-Request-Method","POST").header("Access-Control-Request-Headers","Content-Type")).andExpect(status().isOk());
   mvc.perform(get("/api/test-desktop").header("Origin","https://unrelated.example")).andExpect(status().isForbidden());
  }
 }
}
