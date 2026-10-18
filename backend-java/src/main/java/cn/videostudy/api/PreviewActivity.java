package cn.videostudy.api;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
import java.util.concurrent.atomic.AtomicInteger;

/** Includes synchronous map regeneration and other requests without a queued DB job. */
@Configuration
public class PreviewActivity implements HandlerInterceptor, WebMvcConfigurer {
 private final AtomicInteger running=new AtomicInteger();
 private static final String MARK=PreviewActivity.class.getName();
 public boolean busy(){return running.get()>0;}
 @Override public void addInterceptors(InterceptorRegistry registry){registry.addInterceptor(this).addPathPatterns("/api/**");}
 @Override public boolean preHandle(HttpServletRequest request,HttpServletResponse response,Object handler){
  if(!java.util.Set.of("GET","HEAD","OPTIONS").contains(request.getMethod())){request.setAttribute(MARK,true);running.incrementAndGet();}return true;
 }
 @Override public void afterCompletion(HttpServletRequest request,HttpServletResponse response,Object handler,Exception error){
  if(Boolean.TRUE.equals(request.getAttribute(MARK))){request.removeAttribute(MARK);running.decrementAndGet();}
 }
}
