using System;using System.IO;using System.Collections.Generic;using System.Web.Script.Serialization;using FramewiseSetup;
class ManifestTests {
 static ReleaseManifest Read(string path){return new JavaScriptSerializer().Deserialize<ReleaseManifest>(File.ReadAllText(path));}
 static void Main(string[] args){string path=args[0];var original=Read(path);string url=original.baseUrl+"release.json";int checks=0;
 Action<ReleaseManifest> valid=delegate(ReleaseManifest r){SetupForm.ValidateRelease(r,"0.3.1",url);checks++;};
 Action<Action<ReleaseManifest>> reject=delegate(Action<ReleaseManifest> change){var r=Read(path);change(r);bool failed=false;try{SetupForm.ValidateRelease(r,"0.3.1",url);}catch(InvalidDataException){failed=true;}if(!failed)throw new Exception("invalid manifest accepted");checks++;};
 valid(original);reject(r=>r.schemaVersion=2);reject(r=>r.appVersion="0.3.0");reject(r=>r.baseUrl="https://example.invalid/");reject(r=>r.packages.Clear());reject(r=>r.packages.Add(r.packages[0]));reject(r=>r.packages[0].name="../evil.zip");reject(r=>r.packages[0].sha256="invalid");reject(r=>r.packages[0].size=-1);reject(r=>r.payloadBytes++);reject(r=>r.installer.name="evil.zip");reject(r=>r.installer.size=200000000);Console.WriteLine("manifest validation: "+checks+" checks passed");
 }
}
