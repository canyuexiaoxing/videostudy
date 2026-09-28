package cn.videostudy.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class VideoStudyApplication {
    public static void main(String[] args) {
        SpringApplication.run(VideoStudyApplication.class, args);
    }
}
