using System;using System.IO;using System.Collections.Generic;using System.Web.Script.Serialization;using System.Security.Cryptography;using FramewiseSetup;
class SeedTests {
 static string Sha(byte[] data){using(var s=SHA256.Create())return BitConverter.ToString(s.ComputeHash(data)).Replace("-","").ToLowerInvariant();}
 static void Main(string[] args){string root=args[0],runtime=Path.Combine(root,"runtime"),models=Path.Combine(root,"models");Directory.CreateDirectory(Path.Combine(runtime,"model-seed","group"));byte[] data=new byte[]{1,2,3};File.WriteAllBytes(Path.Combine(runtime,"model-seed/group/model.bin"),data);string manifest=Path.Combine(runtime,"models-manifest.json");
 Action<string,string> write=delegate(string name,string hash){File.WriteAllText(manifest,new JavaScriptSerializer().Serialize(new SeedManifest{files=new List<SeedFile>{new SeedFile{relativePath=name,size=3,sha256=hash}}}));};
 write("group/model.bin",Sha(data));if(ModelSeed.Prepare(runtime,models)!=1)throw new Exception("initial seed");if(ModelSeed.Prepare(runtime,models)!=0)throw new Exception("reuse seed");
 byte[] old=new byte[]{4,5,6};File.WriteAllBytes(Path.Combine(models,"group/model.bin"),old);write("group/model.bin",new string('0',64));bool rejected=false;try{ModelSeed.Prepare(runtime,models);}catch(InvalidDataException){rejected=true;}if(!rejected||File.ReadAllBytes(Path.Combine(models,"group/model.bin"))[0]!=4)throw new Exception("corrupt seed changed existing model");
 write("../escape",Sha(data));rejected=false;try{ModelSeed.Prepare(runtime,models);}catch(InvalidDataException){rejected=true;}if(!rejected)throw new Exception("path escape");Console.WriteLine("model seed: 4 checks passed; temporary fixture only");
 }
}
