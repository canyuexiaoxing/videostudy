using System;
using System.IO;
using System.Text;
using System.Net;
using System.Threading;
using System.Threading.Tasks;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using System.Diagnostics;
namespace FramewiseSetup {
 public sealed class DownloadItem { public string Name; public string Url; public long Size; public string Sha256; }
 public sealed class DownloadUpdate { public string Name; public string Stage; public long Bytes; public long Size; public long Milliseconds; public long NetworkBytes; }
 public sealed class InstallDownload {
  readonly Uri allowed; readonly string cache; readonly bool test;
  public InstallDownload(string allowedBase,string cacheRoot,bool allowLoopback) {
   allowed=new Uri(allowedBase);test=allowLoopback;
   if(allowed.UserInfo!=""||allowed.Query!=""||allowed.Fragment!=""||!allowed.AbsolutePath.EndsWith("/"))throw new InvalidDataException("invalid_base");
   CheckUrl(allowed.AbsoluteUri);cache=Path.GetFullPath(cacheRoot);CheckPlain(cache);Directory.CreateDirectory(cache);CheckPlain(cache);
  }
  public static void CheckPlain(string target) {
   string current=Path.GetFullPath(target);
   while(!String.IsNullOrEmpty(current)) {
    if((Directory.Exists(current)||File.Exists(current))&&(File.GetAttributes(current)&FileAttributes.ReparsePoint)!=0)throw new IOException("linked_path_forbidden");
    current=Path.GetDirectoryName(current);
   }
  }
  public static bool SafeName(string name) {return name!=null&&Regex.IsMatch(name,"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,120}$")&&!Regex.IsMatch(name,"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\\.|$)",RegexOptions.IgnoreCase);}
  void CheckUrl(string source) {
   Uri u=new Uri(source);bool local=test&&u.Scheme=="http"&&u.IsLoopback;
   if((u.Scheme!="https"&&!local)||u.UserInfo!=""||u.Query!=""||u.Fragment!=""||u.GetLeftPart(UriPartial.Authority)!=allowed.GetLeftPart(UriPartial.Authority)||!u.AbsolutePath.StartsWith(allowed.AbsolutePath,StringComparison.Ordinal))throw new InvalidDataException("untrusted_download_url");
  }
  public static string Hash(string file,CancellationToken token) {
   CheckPlain(file);using(var sha=SHA256.Create())using(var f=new FileStream(file,FileMode.Open,FileAccess.Read,FileShare.Read)) {
    byte[] buffer=new byte[1024*1024];int n;while((n=f.Read(buffer,0,buffer.Length))>0){token.ThrowIfCancellationRequested();sha.TransformBlock(buffer,0,n,null,0);}sha.TransformFinalBlock(new byte[0],0,0);return BitConverter.ToString(sha.Hash).Replace("-","").ToLowerInvariant();
   }
  }
  void Report(Action<DownloadUpdate> progress,DownloadItem item,string stage,long bytes,Stopwatch clock,long networkBytes=0){if(progress!=null)progress(new DownloadUpdate{Name=item.Name,Stage=stage,Bytes=bytes,Size=item.Size,Milliseconds=clock.ElapsedMilliseconds,NetworkBytes=networkBytes});}
  public void Fetch(DownloadItem item,CancellationToken token,Action<DownloadUpdate> progress) {
   if(!SafeName(item.Name)||item.Size<=0||item.Size>16L*1024*1024*1024||!Regex.IsMatch(item.Sha256??"","^[a-f0-9]{64}$"))throw new InvalidDataException("invalid_download_item");CheckUrl(item.Url);
   string target=Path.Combine(cache,item.Name),part=target+".part";CheckPlain(target);CheckPlain(part);var clock=Stopwatch.StartNew();long transferred=0;
   if(File.Exists(target)){Report(progress,item,"verifying",0,clock);if(new FileInfo(target).Length==item.Size&&Hash(target,token)==item.Sha256){Report(progress,item,"cached",item.Size,clock);return;}File.Delete(target);}
   for(int attempt=0;attempt<3;attempt++) {
    token.ThrowIfCancellationRequested();CheckPlain(part);
    try {
     long offset=File.Exists(part)?new FileInfo(part).Length:0;
     if(offset>item.Size){File.Delete(part);offset=0;}
     if(offset<item.Size) {
      var request=(HttpWebRequest)WebRequest.Create(item.Url);request.AllowAutoRedirect=false;request.Timeout=30000;request.ReadWriteTimeout=30000;request.AutomaticDecompression=DecompressionMethods.None;request.UserAgent="Framewise-Installer/1";
      if(offset>0)request.AddRange(offset);
      using(token.Register(delegate{request.Abort();}))
      using(var response=(HttpWebResponse)request.GetResponse()) {
       int status=(int)response.StatusCode;
       if(status==200){offset=0;}else if(status==206) {
        string expected="bytes "+offset+"-"+(item.Size-1)+"/"+item.Size;
        if(offset==0||response.Headers["Content-Range"]!=expected){File.Delete(part);throw new InvalidDataException("invalid_content_range");}
       }else throw new InvalidDataException("unexpected_http_status_"+status);
       if(response.ContentLength>=0&&response.ContentLength!=item.Size-offset)throw new InvalidDataException("invalid_content_length");
       using(var input=response.GetResponseStream())using(var output=new FileStream(part,offset>0?FileMode.Append:FileMode.Create,FileAccess.Write,FileShare.Read)) {
        byte[] buffer=new byte[128*1024];long received=offset;int n;long last=-1000;
        while((n=input.Read(buffer,0,buffer.Length))>0){token.ThrowIfCancellationRequested();if(n>item.Size-received)throw new InvalidDataException("download_too_large");output.Write(buffer,0,n);received+=n;transferred+=n;if(clock.ElapsedMilliseconds-last>=150){Report(progress,item,"downloading",received,clock,transferred);last=clock.ElapsedMilliseconds;}}
        output.Flush(true);if(received!=item.Size)throw new IOException("incomplete_download");
       }
      }
     }
     Report(progress,item,"verifying",item.Size,clock);
     if(Hash(part,token)!=item.Sha256){File.Delete(part);throw new InvalidDataException("checksum_mismatch");}
     CheckPlain(target);File.Move(part,target);Report(progress,item,"completed",item.Size,clock);return;
    }catch(Exception error) {
     if(token.IsCancellationRequested)throw new OperationCanceledException(token);
     var web=error as WebException;var res=web==null?null:web.Response as HttpWebResponse;int status=res==null?0:(int)res.StatusCode;if(res!=null)res.Close();
     if(status>=400&&status<500&&status!=408&&status!=429)throw new IOException("http_"+status);
     if(attempt==2)throw;
     Report(progress,item,"retrying",0,clock);if(token.WaitHandle.WaitOne(500*(attempt+1)))token.ThrowIfCancellationRequested();
    }
   }
  }
 }
}
