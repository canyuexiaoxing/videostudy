package cn.videostudy.api;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Set;

/** The desktop main process holds this per-launch capability; browser pages never receive it. */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class NativeRuntimeFilter extends OncePerRequestFilter {
 public static final String HEADER="X-Framewise-Runtime";
 private static final Set<String> ORIGINS=Set.of("app://framewise","app://videostudy","http://127.0.0.1:5173","http://localhost:5173");
 private final byte[] token;
 public NativeRuntimeFilter(@Value("${FRAMEWISE_RUNTIME_TOKEN:}") String token){this.token=token.getBytes(StandardCharsets.UTF_8);}
 @Override protected boolean shouldNotFilter(HttpServletRequest request){String path=request.getRequestURI().substring(request.getContextPath().length());return token.length==0||!(path.equals("/api")||path.startsWith("/api/"));}
 @Override protected void doFilterInternal(HttpServletRequest request,HttpServletResponse response,FilterChain chain)throws ServletException,IOException {
  if("OPTIONS".equals(request.getMethod())&&request.getHeader("Origin")!=null&&ORIGINS.contains(request.getHeader("Origin"))){chain.doFilter(request,response);return;}
  String supplied=request.getHeader(HEADER);
  if(supplied==null||!MessageDigest.isEqual(token,supplied.getBytes(StandardCharsets.UTF_8))){response.setStatus(403);response.setContentType("application/json");response.getWriter().write("{\"error\":\"runtime_unauthorized\"}");return;}
  chain.doFilter(request,response);
 }
}
