package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
class NativeRuntimeFilterTest {
 @RestController static class Endpoint {@GetMapping({"/api/health","/api/runtime/health","/public"}) public String get(){return "ok";}@RequestMapping(value="/api/runtime/health",method=RequestMethod.OPTIONS) public String options(){return "ok";}}
 private MockMvc mvc(String token){return MockMvcBuilders.standaloneSetup(new Endpoint()).addFilters(new NativeRuntimeFilter(token)).build();}
 @Test void nativeApiIncludingHealthRequiresExactPrivateToken()throws Exception{
  var mvc=mvc("test-private-capability");
  for(String path:new String[]{"/api/health","/api/runtime/health"}){
   mvc.perform(get(path)).andExpect(status().isForbidden()).andExpect(content().json("{\"error\":\"runtime_unauthorized\"}"));
   mvc.perform(get(path).header(NativeRuntimeFilter.HEADER,"incorrect")).andExpect(status().isForbidden());
   mvc.perform(get(path).header(NativeRuntimeFilter.HEADER,"test-private-capability")).andExpect(status().isOk());
  }
  mvc.perform(get("/public")).andExpect(status().isOk());
 }
 @Test void legacyDockerModeWithoutTokenRemainsAccessible()throws Exception{mvc("").perform(get("/api/health")).andExpect(status().isOk());}
 @Test void trustedPreflightDoesNotNeedTokenButUnknownOriginDoes()throws Exception{
  var mvc=mvc("test-private-capability");
  mvc.perform(options("/api/runtime/health").header("Origin","app://framewise")).andExpect(status().isOk());
  mvc.perform(options("/api/runtime/health").header("Origin","https://unrelated.example")).andExpect(status().isForbidden());
  mvc.perform(options("/api/runtime/health")).andExpect(status().isForbidden());
 }
}
