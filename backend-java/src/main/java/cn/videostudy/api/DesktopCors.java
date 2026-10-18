package cn.videostudy.api;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
/** Keep normal browser origins and permit only the packaged application's stable origin. */
@Configuration
public class DesktopCors implements WebMvcConfigurer {
 @Override public void addCorsMappings(CorsRegistry registry){registry.addMapping("/api/**").allowedOrigins("http://127.0.0.1:5173","http://localhost:5173","app://framewise").allowedMethods("GET","HEAD","POST","PUT","PATCH","DELETE","OPTIONS").allowedHeaders("*").maxAge(3600);}
}
