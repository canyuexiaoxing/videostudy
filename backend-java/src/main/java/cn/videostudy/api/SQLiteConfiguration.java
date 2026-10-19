package cn.videostudy.api;
import org.springframework.context.annotation.*;
import org.springframework.beans.factory.annotation.Value;
import javax.sql.DataSource;
import java.nio.file.*;
import com.zaxxer.hikari.*;
@Configuration
@Profile("sqlite")
public class SQLiteConfiguration {
 @Bean public DataSource dataSource(@Value("${framewise.sqlite.path}") String filename)throws java.io.IOException{
  var path=Path.of(filename).toAbsolutePath().normalize();Files.createDirectories(path.getParent());
  var config=new HikariConfig();config.setJdbcUrl("jdbc:sqlite:"+path);config.setDriverClassName("org.sqlite.JDBC");config.setMaximumPoolSize(4);config.setMinimumIdle(1);
  config.addDataSourceProperty("foreign_keys","true");config.addDataSourceProperty("busy_timeout","10000");config.addDataSourceProperty("journal_mode","WAL");config.addDataSourceProperty("date_class","TEXT");config.addDataSourceProperty("transaction_mode","IMMEDIATE");config.setPoolName("framewise-sqlite");return new HikariDataSource(config);
 }
}
