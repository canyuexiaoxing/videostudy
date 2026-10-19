package cn.videostudy.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class VideoStudyApplication {
    public static void main(String[] args) {
        boolean cloud="cloud".equals(System.getenv("FRAMEWISE_ROLE"))||java.util.Arrays.asList(args).contains("--framewise.role=cloud");
        SpringApplication.run(cloud?cn.videostudy.cloud.CloudSyncApplication.class:VideoStudyApplication.class, args);
    }
}
