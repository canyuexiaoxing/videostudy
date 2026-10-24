using System;using System.Net;using System.IO;using System.Linq;using System.Text;using System.Collections.Generic;using System.Diagnostics;using System.Threading;using System.Threading.Tasks;using System.Windows.Forms;using System.Drawing;using System.Web.Script.Serialization;
namespace FramewiseSetup {
 public sealed class Package {public string name;public long size;public string sha256;public long unpackedBytes;public int fileCount;public string component;}
 public sealed class ReleaseManifest {public string format;public int schemaVersion;public string appVersion;public string releaseId;public string platform;public string baseUrl;public List<Package> packages;public Package installer;public long payloadBytes;}
 public sealed class SetupForm:Form {
  readonly Label title=new Label(),intro=new Label(),state=new Label(),details=new Label(),notice=new Label();readonly TextBox destination=new TextBox();readonly Button browse=new Button(),start=new Button(),pause=new Button();readonly ProgressBar bar=new ProgressBar();
  readonly CheckBox cleanup=new CheckBox();readonly string requestId=Guid.NewGuid().ToString("N");readonly string cache;CancellationTokenSource cancellation;bool busy,closing,installing,finished;long prefix,total;Stopwatch clock;ReleaseManifest manifest;
  public SetupForm(){
   Text="Framewise 在线安装";Size=new Size(820,540);MinimumSize=new Size(740,510);FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;StartPosition=FormStartPosition.CenterScreen;Font=new Font("Microsoft YaHei UI",10);BackColor=Color.White;Icon=Icon.ExtractAssociatedIcon(Application.ExecutablePath);AutoScaleMode=AutoScaleMode.Dpi;
   title.Text="安装 Framewise "+ReleaseInfo.Version;title.Font=new Font("Microsoft YaHei UI",22,FontStyle.Bold);title.SetBounds(32,28,740,45);
   intro.Text="自动下载程序、运行环境和必要模型，安装后在本机处理课程视频。\n下载约"+Pretty(ReleaseInfo.DownloadBytes)+"，安装后约"+Pretty(ReleaseInfo.PayloadBytes);intro.SetBounds(34,82,730,42);
   var folderLabel=new Label{Text="安装位置",Left=34,Top=140,Width=200};destination.SetBounds(34,172,614,32);destination.Text=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Programs","Framewise");browse.Text="浏览…";browse.SetBounds(662,170,104,35);browse.Click+=delegate{using(var d=new FolderBrowserDialog()){d.Description="选择Framewise安装目录";d.SelectedPath=destination.Text;if(d.ShowDialog(this)==DialogResult.OK)destination.Text=d.SelectedPath;}};
   state.Text="准备就绪";state.SetBounds(34,230,730,28);state.Font=new Font(Font,FontStyle.Bold);bar.SetBounds(34,268,732,16);bar.Maximum=1000;
   details.Text="下载失败可重试；暂停或关闭后，已下载内容会保留。";details.SetBounds(34,298,732,45);
   notice.Text="课程、笔记和API设置保留在原用户数据目录。AI功能联网并使用你配置的API。\n此安装器未进行代码签名；首次运行可能出现Windows安全提示。";notice.ForeColor=Color.DimGray;notice.SetBounds(34,355,732,58);
   start.Text="开始安装";start.SetBounds(620,430,146,42);start.BackColor=Color.FromArgb(49,90,222);start.ForeColor=Color.White;start.FlatStyle=FlatStyle.Flat;start.Click+=async delegate{if(finished){Close();return;}await RunAsync();};
   pause.Text="暂停下载";pause.SetBounds(466,430,138,42);pause.Enabled=false;pause.Click+=delegate{cancellation.Cancel();pause.Enabled=false;state.Text="正在暂停，保留下载进度…";};
   cleanup.Text="安装成功后清理下载缓存";cleanup.Checked=true;cleanup.SetBounds(34,433,360,32);
   foreach(Control control in new Control[]{cleanup,title,intro,folderLabel,destination,browse,state,bar,details,notice,start,pause})Controls.Add(control);
   cache=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Framewise","InstallerCache",ReleaseInfo.Version+"-"+ReleaseInfo.ManifestHash.Substring(0,16));
   FormClosing+=delegate(object sender,FormClosingEventArgs e){if(installing){e.Cancel=true;MessageBox.Show(this,"正在解压安装，请等待安装结束。","Framewise");return;}if(busy){e.Cancel=true;closing=true;cancellation.Cancel();}};
  }
  static string Pretty(long value){return (value/1000000000.0).ToString("0.00")+" GB";}
  void Log(string stage,string result){try{InstallDownload.CheckPlain(cache);Directory.CreateDirectory(cache);InstallDownload.CheckPlain(cache);string file=Path.Combine(cache,"installer-events.jsonl");InstallDownload.CheckPlain(file);if(File.Exists(file)&&new FileInfo(file).Length>1024*1024)File.Delete(file);File.AppendAllText(file,new JavaScriptSerializer().Serialize(new {timestamp=DateTime.UtcNow.ToString("o"),stage=stage,result=result,requestId=requestId,version=ReleaseInfo.Version,elapsedMs=clock==null?0:clock.ElapsedMilliseconds})+Environment.NewLine,Encoding.UTF8);}catch{}}
  void Progress(DownloadUpdate u){if(IsDisposed)return;long displayed=Math.Min(total,prefix+u.Bytes);BeginInvoke((Action)delegate{if(IsDisposed)return;string label=u.Stage=="verifying"?"正在校验":u.Stage=="cached"?"复用已校验文件":u.Stage=="retrying"?"下载中断，正在重试":"正在下载";state.Text=label+"："+u.Name;long current=displayed;bar.Value=total==0?0:(int)Math.Min(1000,current*1000/total);details.Text=Pretty(current)+" / "+Pretty(total)+"   "+(u.Stage!="downloading"?"":(u.NetworkBytes/1024.0/1024/Math.Max(.1,u.Milliseconds/1000.0)).ToString("0.0")+" MB/s")+"\n运行环境体积较大，请保持网络连接。";});}
  DownloadItem Item(Package p){return new DownloadItem{Name=p.name,Url=manifest.baseUrl+p.name,Size=p.size,Sha256=p.sha256};}
  public static void ValidateRelease(ReleaseManifest r,string version,string manifestUrl){
   string expected=manifestUrl.Substring(0,manifestUrl.LastIndexOf('/')+1);
   if(r==null||r.format!="framewise-online-release"||r.schemaVersion!=1||r.platform!="windows-x64"||r.appVersion!=version||r.baseUrl!=expected||!InstallDownload.SafeName(r.releaseId)||!expected.EndsWith("/"+r.releaseId+"/")||r.packages==null||r.packages.Count==0||r.packages.Count>128||r.installer==null)throw new InvalidDataException("invalid_manifest");
   var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);long expanded=0;foreach(var p in r.packages){if(!InstallDownload.SafeName(p.name)||!p.name.EndsWith(".zip")||p.size<=0||p.size>16L*1024*1024*1024||!System.Text.RegularExpressions.Regex.IsMatch(p.sha256??"","^[a-f0-9]{64}$")||p.unpackedBytes<0||p.fileCount<=0||!names.Add(p.name))throw new InvalidDataException("invalid_manifest_package");expanded=checked(expanded+p.unpackedBytes);}
   if(expanded!=r.payloadBytes||expanded<=0||expanded>128L*1024*1024*1024||!InstallDownload.SafeName(r.installer.name)||!r.installer.name.EndsWith(".exe")||r.installer.size<=0||r.installer.size>100*1024*1024||!System.Text.RegularExpressions.Regex.IsMatch(r.installer.sha256??"","^[a-f0-9]{64}$")||!names.Add(r.installer.name))throw new InvalidDataException("invalid_manifest_size");
  }
  string Target(){string path=Path.GetFullPath(destination.Text.Trim());if(path.StartsWith(@"\\")||path.Length>160||path.TrimEnd('\\')==Path.GetPathRoot(path).TrimEnd('\\'))throw new IOException("invalid_install_folder");InstallDownload.CheckPlain(path);return path;}
  void Space(string target){long need=0;foreach(var p in manifest.packages.Concat(new[]{manifest.installer})){long have=0;foreach(string suffix in new[]{"",".part"}){string path=Path.Combine(cache,p.name)+suffix;InstallDownload.CheckPlain(path);if(File.Exists(path))have=Math.Max(have,Math.Min(p.size,new FileInfo(path).Length));}need=checked(need+p.size-have);}long margin=1024L*1024*1024;
   var cacheDrive=new DriveInfo(Path.GetPathRoot(cache));var targetDrive=new DriveInfo(Path.GetPathRoot(target));if(cacheDrive.Name.Equals(targetDrive.Name,StringComparison.OrdinalIgnoreCase)){if(cacheDrive.AvailableFreeSpace<need+manifest.payloadBytes+margin)throw new IOException("insufficient_disk_space");}else if(cacheDrive.AvailableFreeSpace<need+margin||targetDrive.AvailableFreeSpace<manifest.payloadBytes+margin)throw new IOException("insufficient_disk_space");
  }
  async Task RunAsync(){
   if(busy)return;string target;try{target=Target();}catch(Exception){MessageBox.Show(this,"请选择正常的本机程序文件夹，不能是磁盘根目录、网络盘或目录链接。","安装位置无效");return;}
   busy=true;start.Enabled=false;browse.Enabled=false;destination.Enabled=false;pause.Enabled=true;bar.Style=ProgressBarStyle.Continuous;cancellation=new CancellationTokenSource();clock=Stopwatch.StartNew();Log("download","started");
   try {
    await Task.Run(delegate{
     string baseUrl=ReleaseInfo.ManifestUrl.Substring(0,ReleaseInfo.ManifestUrl.LastIndexOf('/')+1);var loader=new InstallDownload(baseUrl,cache,false);
     loader.Fetch(new DownloadItem{Name="release.json",Url=ReleaseInfo.ManifestUrl,Size=ReleaseInfo.ManifestSize,Sha256=ReleaseInfo.ManifestHash},cancellation.Token,null);
     string raw=File.ReadAllText(Path.Combine(cache,"release.json"),Encoding.UTF8);if(raw.Length>1024*1024)throw new InvalidDataException("manifest_too_large");manifest=new JavaScriptSerializer().Deserialize<ReleaseManifest>(raw);ValidateRelease(manifest,ReleaseInfo.Version,ReleaseInfo.ManifestUrl);Space(target);
     total=manifest.packages.Sum(p=>p.size)+manifest.installer.size;prefix=0;
     foreach(var package in manifest.packages.Concat(new[]{manifest.installer})){Log("download_"+package.name,"started");loader.Fetch(Item(package),cancellation.Token,Progress);Log("download_"+package.name,"completed");prefix+=package.size;}
    });
    cancellation.Token.ThrowIfCancellationRequested();
    if(Process.GetProcessesByName("Framewise").Any())throw new IOException("framewise_running");
    pause.Enabled=false;installing=true;state.Text="文件校验完成，正在解压安装…";bar.Style=ProgressBarStyle.Marquee;details.Text="安装过程中请勿关闭窗口。原课程、笔记和API设置保留。";Log("install","started");
    string core=Path.Combine(cache,manifest.installer.name);InstallDownload.CheckPlain(core);if(InstallDownload.Hash(core,CancellationToken.None)!=manifest.installer.sha256)throw new IOException("installer_checksum_mismatch");
    string log=Path.Combine(cache,"install-core.log");var info=new ProcessStartInfo(core,"/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="+Quote(target)+" /TASKS=desktopicon /DOWNLOADCACHE="+Quote(cache)+" /LOG="+Quote(log)){UseShellExecute=false,CreateNoWindow=true,WindowStyle=ProcessWindowStyle.Hidden};
    using(var process=Process.Start(info)){await Task.Run((Action)process.WaitForExit);if(process.ExitCode!=0)throw new IOException("install_core_"+process.ExitCode);}
    string exe=Path.Combine(target,"versions",ReleaseInfo.Version,"Framewise.exe");if(!File.Exists(exe))throw new IOException("installed_executable_missing");
    state.Text="正在准备本地模型…";Log("model_seed","started");
    string modelRoot=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),"Framewise","data","models");
    await Task.Run(delegate{ModelSeed.Prepare(Path.Combine(target,"versions",ReleaseInfo.Version,"resources","runtime"),modelRoot);});Log("model_seed","completed");
    if(cleanup.Checked){foreach(var package in manifest.packages.Concat(new[]{manifest.installer})){try{string cached=Path.Combine(cache,package.name);InstallDownload.CheckPlain(cached);File.Delete(cached);}catch{Log("cache_cleanup","deferred");}}}
    installing=false;finished=true;bar.Style=ProgressBarStyle.Continuous;bar.Value=1000;state.Text="Framewise 安装完成";details.Text="可通过桌面或开始菜单快捷方式启动。首次打开后，在设置中配置个人API。";start.Text="完成";Log("install","completed");
   }catch(OperationCanceledException){Log("download","paused");state.Text="下载已暂停";details.Text="进度已保留，点击继续下载即可恢复。";start.Text="继续下载";}
   catch(Exception e){installing=false;Log("setup","failed_"+e.GetType().Name+"_"+(System.Text.RegularExpressions.Regex.IsMatch(e.Message,"^[a-zA-Z0-9_]{1,80}$")?e.Message:"unclassified"));state.Text="安装尚未完成";details.Text=Explain(e);start.Text="重试";bar.Style=ProgressBarStyle.Continuous;}
   finally{installing=false;busy=false;pause.Enabled=false;start.Enabled=true;browse.Enabled=!finished;destination.Enabled=!finished;if(closing){closing=false;Close();}}
  }
  static string Quote(string value){return "\""+value.Replace("\"","").TrimEnd('\\')+"\"";}
  static string Explain(Exception e){string code=e.Message;
   if(code=="framewise_running")return "请先关闭正在运行的Framewise，再点击重试；已下载文件会复用。";
   if(code=="insufficient_disk_space")return "空间不足。安装需要下载缓存和完整程序空间，可更换安装位置或清理磁盘后重试。";
   if(code=="http_403")return "下载权限不足：发布对象尚未开放读取，请联系发布者。";
   if(code=="http_404")return "发布文件不存在：可能尚未上传完整，请联系发布者。";
   if(code.IndexOf("checksum",StringComparison.OrdinalIgnoreCase)>=0)return "文件完整性检查失败，请重试。损坏的包不会用于安装。";
   if(code.StartsWith("install_core_"))return "安装组件返回失败（"+code+"）。日志保存在本机安装缓存目录，已下载文件保留。";
   if(e is WebException||e is IOException)return "网络或本机文件操作失败。检查网络和磁盘后重试；已下载内容会保留。";
   return "发布文件或安装配置未通过检查，请联系发布者。已下载文件保留。";
  }
#if QA
  public void SavePreview(string path){ShowInTaskbar=false;StartPosition=FormStartPosition.Manual;Location=new Point(-32000,-32000);Show();Application.DoEvents();foreach(Control control in Controls)control.CreateControl();using(var b=new Bitmap(Width,Height)){DrawToBitmap(b,new Rectangle(0,0,Width,Height));b.Save(path);}}
#endif
 }
 static class Program {
  [STAThread]static void Main(string[] args){System.Net.ServicePointManager.SecurityProtocol=System.Net.SecurityProtocolType.Tls12;Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
#if QA
   if(args.Length==2&&args[0]=="--qa-layout"){using(var form=new SetupForm())form.SavePreview(args[1]);return;}
#endif
   if(Environment.OSVersion.Version.Major<10||Environment.OSVersion.Version.Build<17763){MessageBox.Show("需要Windows 10 1809或更新的64位系统。");return;}
   using(var mutex=new Mutex(false,"Local\\FramewiseOnlineInstaller")){bool owns=false;try{owns=mutex.WaitOne(0);}catch(AbandonedMutexException){owns=true;}if(!owns){MessageBox.Show("已有一个Framewise安装器正在运行。");return;}try{Application.Run(new SetupForm());}finally{mutex.ReleaseMutex();}}
  }
 }
}
