using System;using System.IO;using System.Threading;using System.Security.Cryptography;using FramewiseSetup;
class DownloadTests {
 static int passed=0;static void Check(bool value,string name){if(!value)throw new Exception("FAILED: "+name);passed++;Console.WriteLine("PASS "+name);}
 static string Sha(byte[] data){using(var s=SHA256.Create())return BitConverter.ToString(s.ComputeHash(data)).Replace("-","").ToLowerInvariant();}
 static void Main(string[] args){string url=args[0],folder=args[1];byte[] data=new byte[200000];for(int i=0;i<data.Length;i++)data[i]=(byte)(i%251);string hash=Sha(data);
 Check(!InstallDownload.SafeName("../bad")&&!InstallDownload.SafeName("CON.zip")&&!InstallDownload.SafeName("a.zip:stream")&&InstallDownload.SafeName("app-001.zip"),"safe_names");
 var downloader=new InstallDownload(url,folder,true);
 Action<string,string> test=delegate(string endpoint,string name){downloader.Fetch(new DownloadItem{Name=name,Url=url+endpoint,Size=data.Length,Sha256=hash},CancellationToken.None,null);Check(InstallDownload.Hash(Path.Combine(folder,name),CancellationToken.None)==hash,name);};
 test("file","normal.zip");
 File.WriteAllBytes(Path.Combine(folder,"resume.zip.part"),new ArraySegment<byte>(data,0,50000).ToArrayCompat());test("file","resume.zip");
 File.WriteAllBytes(Path.Combine(folder,"restart.zip.part"),new ArraySegment<byte>(data,0,50000).ToArrayCompat());test("ignore-range","restart.zip");
 File.WriteAllBytes(Path.Combine(folder,"bad-range.zip.part"),new ArraySegment<byte>(data,0,50000).ToArrayCompat());test("bad-range-once","bad-range.zip");
 test("interrupt-once","interrupt.zip");
 File.WriteAllBytes(Path.Combine(folder,"corrupt.zip.part"),new byte[200000]);test("file","corrupt.zip");
 bool rejected=false;try{test("wrong","hash-fail.zip");}catch(InvalidDataException){rejected=true;}Check(rejected&&!File.Exists(Path.Combine(folder,"hash-fail.zip")),"checksum_rejects");
 rejected=false;try{test("missing","missing.zip");}catch(IOException e){rejected=e.Message=="http_404";}Check(rejected,"http_404_clear");
 rejected=false;try{test("redirect","redirect.zip");}catch(InvalidDataException){rejected=true;}Check(rejected,"no_redirect_to_untrusted_host");
 var cancel=new CancellationTokenSource();cancel.Cancel();rejected=false;try{downloader.Fetch(new DownloadItem{Name="cancel.zip",Url=url+"file",Size=data.Length,Sha256=hash},cancel.Token,null);}catch(OperationCanceledException){rejected=true;}Check(rejected,"cancel");
 var mid=new CancellationTokenSource();mid.CancelAfter(150);rejected=false;try{downloader.Fetch(new DownloadItem{Name="midcancel.zip",Url=url+"slow",Size=data.Length,Sha256=hash},mid.Token,null);}catch(OperationCanceledException){rejected=true;}Check(rejected&&File.Exists(Path.Combine(folder,"midcancel.zip.part"))&&new FileInfo(Path.Combine(folder,"midcancel.zip.part")).Length>0,"cancel_keeps_partial");test("file","midcancel.zip");
 Console.WriteLine("TOTAL "+passed);
 }
}
static class Extensions {public static byte[] ToArrayCompat(this ArraySegment<byte> value){var result=new byte[value.Count];Array.Copy(value.Array,value.Offset,result,0,value.Count);return result;}}
