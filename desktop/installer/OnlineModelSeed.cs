using System;using System.IO;using System.Text.RegularExpressions;using System.Threading;using System.Web.Script.Serialization;using System.Collections.Generic;
namespace FramewiseSetup {
 public sealed class SeedFile {public string relativePath;public long size;public string sha256;}
 public sealed class SeedManifest {public List<SeedFile> files;}
 public static class ModelSeed {
  public static int Prepare(string runtime,string modelRoot) {
   InstallDownload.CheckPlain(runtime);InstallDownload.CheckPlain(modelRoot);var manifestPath=Path.Combine(runtime,"models-manifest.json");InstallDownload.CheckPlain(manifestPath);
   if(new FileInfo(manifestPath).Length>1024*1024)throw new InvalidDataException("invalid_model_manifest");
   var m=new JavaScriptSerializer().Deserialize<SeedManifest>(File.ReadAllText(manifestPath));if(m==null||m.files==null||m.files.Count==0||m.files.Count>128)throw new InvalidDataException("invalid_model_manifest");
   var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);int prepared=0;
   foreach(var f in m.files) {
    if(f.relativePath==null||f.size<=0||f.size>2L*1024*1024*1024||!Regex.IsMatch(f.sha256??"","^[a-f0-9]{64}$"))throw new InvalidDataException("invalid_model_manifest");
    foreach(var segment in f.relativePath.Split('/'))if(!InstallDownload.SafeName(segment)||segment=="."||segment=="..")throw new InvalidDataException("invalid_model_path");
    if(!names.Add(f.relativePath))throw new InvalidDataException("duplicate_model_path");
    string relative=f.relativePath.Replace('/',Path.DirectorySeparatorChar),source=Path.Combine(runtime,"model-seed",relative),target=Path.Combine(modelRoot,relative);
    InstallDownload.CheckPlain(source);InstallDownload.CheckPlain(target);
    if(File.Exists(target)&&new FileInfo(target).Length==f.size&&InstallDownload.Hash(target,CancellationToken.None)==f.sha256)continue;
    if(!File.Exists(source)||new FileInfo(source).Length!=f.size)throw new InvalidDataException("model_seed_missing");
    Directory.CreateDirectory(Path.GetDirectoryName(target));string temp=target+".install-"+Guid.NewGuid().ToString("N")+".part";
    try {
     using(var input=File.OpenRead(source))using(var output=new FileStream(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None)){input.CopyTo(output);output.Flush(true);}
     if(InstallDownload.Hash(temp,CancellationToken.None)!=f.sha256)throw new InvalidDataException("model_seed_checksum_mismatch");
     InstallDownload.CheckPlain(target);if(File.Exists(target))File.Replace(temp,target,null);else File.Move(temp,target);prepared++;
    }finally {if(File.Exists(temp))File.Delete(temp);}
   }
   return prepared;
  }
 }
}
