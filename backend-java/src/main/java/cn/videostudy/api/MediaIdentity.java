package cn.videostudy.api;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
public record MediaIdentity(long size,String fingerprint) {
 public static MediaIdentity read(Path file) throws IOException {
  try(var channel=FileChannel.open(file,StandardOpenOption.READ)){
   long size=channel.size();var digest=MessageDigest.getInstance("SHA-256");digest.update(ByteBuffer.allocate(8).putLong(size).array());
   digest.update(sample(channel,0,(int)Math.min(size,65536)));digest.update(sample(channel,Math.max(0,size-65536),(int)Math.min(size,65536)));
   if(channel.size()!=size)throw new IOException("media_changed");
   return new MediaIdentity(size,HexFormat.of().formatHex(digest.digest()));
  }catch(NoSuchAlgorithmException error){throw new IllegalStateException(error);}
 }
 private static byte[] sample(FileChannel channel,long position,int length)throws IOException{var buffer=ByteBuffer.allocate(length);while(buffer.hasRemaining()){int count=channel.read(buffer,position+buffer.position());if(count<0)throw new IOException("media_truncated");}return buffer.array();}
}
