package cn.videostudy.api;
import org.springframework.jdbc.core.JdbcTemplate;
final class DatabaseDialect {
 static Object timestamp(java.time.Instant value,boolean sqlite){return sqlite?java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS").withZone(java.time.ZoneOffset.UTC).format(value):java.sql.Timestamp.from(value);}
 static java.time.Instant instant(java.sql.ResultSet row,String column,boolean sqlite)throws java.sql.SQLException{return sqlite?java.sql.Timestamp.valueOf(row.getString(column)).toLocalDateTime().toInstant(java.time.ZoneOffset.UTC):row.getTimestamp(column).toInstant();}
 static boolean duplicate(org.springframework.dao.DataAccessException error){if(error instanceof org.springframework.dao.DuplicateKeyException)return true;for(Throwable cause=error;cause!=null;cause=cause.getCause())if(cause instanceof org.sqlite.SQLiteException sqlite)return sqlite.getResultCode()==org.sqlite.SQLiteErrorCode.SQLITE_CONSTRAINT_UNIQUE||sqlite.getResultCode()==org.sqlite.SQLiteErrorCode.SQLITE_CONSTRAINT_PRIMARYKEY;return false;}
 static boolean sqlite(JdbcTemplate jdbc){try(var c=java.util.Objects.requireNonNull(jdbc.getDataSource()).getConnection()){return c.getMetaData().getDatabaseProductName().equalsIgnoreCase("SQLite");}catch(java.sql.SQLException e){throw new IllegalStateException("Database metadata unavailable",e);}}
}
