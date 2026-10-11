from pathlib import Path
p=Path('E:/workp/videostudy/backend-java')
f=p/'src/main/java/cn/videostudy/api/IgnoreRegion.java';s=f.read_text(encoding='utf-8')
s=s.replace('List<TimedRegion> nodes) {', 'List<TimedRegion> nodes, IgnoreRegion analysisRegion, IgnoreRegion ignoredRegion, boolean allowFull) {',1)
s=s.replace('(region!=null&&region.nodes()!=null)', '(region!=null&&(region.nodes()!=null||region.analysisRegion()!=null||region.ignoredRegion()!=null))')
s=s.replace('    public IgnoreRegion(double x,double y,double width,double height) { this(x,y,width,height,null); }', '''    public IgnoreRegion(double x,double y,double width,double height) { this(x,y,width,height,null); }
    public IgnoreRegion(double x,double y,double width,double height,List<TimedRegion> nodes){this(x,y,width,height,nodes,null,null,false);}''')
s=s.replace('        if(nodes!=null) {', '''        if(analysisRegion!=null||ignoredRegion!=null){
            if(x!=0||y!=0||width!=0||height!=0||nodes!=null||allowFull)throw new IllegalArgumentException("invalid_media_regions");
            for(var child:new IgnoreRegion[]{analysisRegion,ignoredRegion})if(child!=null&&(child.analysisRegion()!=null||child.ignoredRegion()!=null))throw new IllegalArgumentException("invalid_media_regions");
            var times=new java.util.TreeSet<Long>();times.add(0L);
            for(var child:new IgnoreRegion[]{analysisRegion,ignoredRegion})if(child!=null&&child.nodes()!=null)for(var node:child.nodes())times.add(node.timeMs());
            for(var time:times){var a=at(analysisRegion,time);var b=at(ignoredRegion,time);if(a!=null&&b!=null&&b.x()<=a.x()&&b.y()<=a.y()&&b.x()+b.width()>=a.x()+a.width()&&b.y()+b.height()>=a.y()+a.height())throw new IllegalArgumentException("analysis_region_fully_ignored");}
        } else if(nodes!=null) {''',1)
s=s.replace('||width*height>.95)', '||(!allowFull&&width*height>.95))')
s=s.replace('        return nodes==null?', '''        if(analysisRegion!=null||ignoredRegion!=null){var result=new java.util.LinkedHashMap<String,Object>();result.put("analysisRegion",analysisRegion);result.put("ignoredRegion",ignoredRegion);return result;}
        return nodes==null?''')
s=s.replace('    private static IgnoreRegion rectangle(JsonNode node) {','    private static IgnoreRegion rectangle(JsonNode node,boolean analysis) {')
s=s.replace('node.get("height").doubleValue());', 'node.get("height").doubleValue(),null,null,null,analysis);')
start=s.index('                if(!node.has("nodes"))');end=s.index('\n            }\n        } catch',start)
s=s[:start]+'''                return fromNode(node,false);
'''+s[end:]
insert='''    private static IgnoreRegion at(IgnoreRegion value,long time){if(value==null||value.nodes()==null)return value;IgnoreRegion region=null;for(var node:value.nodes()){if(node.timeMs()>time)break;region=node.region();}return region;}
    private static IgnoreRegion fromNode(JsonNode node,boolean analysis){
        if(node==null||node.isNull())return null;
        if(!node.isObject())throw new IllegalArgumentException("invalid_ignored_region");
        if(node.has("analysisRegion")||node.has("ignoredRegion")){
            if(analysis||node.size()!=2||!node.has("analysisRegion")||!node.has("ignoredRegion"))throw new IllegalArgumentException("invalid_media_regions");
            for(var child:List.of(node.get("analysisRegion"),node.get("ignoredRegion")))if(child.isObject()&&(child.has("analysisRegion")||child.has("ignoredRegion")))throw new IllegalArgumentException("invalid_media_regions");
            var a=fromNode(node.get("analysisRegion"),true);var b=fromNode(node.get("ignoredRegion"),false);
            if(a==null&&b==null)return null;
            return new IgnoreRegion(0,0,0,0,null,a,b,false);
        }
        if(!node.has("nodes"))return rectangle(node,analysis);
        if(node.size()!=1||!node.get("nodes").isArray()||node.get("nodes").size()>200)throw new IllegalArgumentException("invalid_ignored_region");
        var nodes=new java.util.ArrayList<TimedRegion>();
        for(var item:node.get("nodes")){
            if(!item.isObject()||item.size()!=2||!item.has("timeMs")||!item.get("timeMs").isIntegralNumber()||!item.get("timeMs").canConvertToLong()||!item.has("region"))throw new IllegalArgumentException("invalid_ignored_region");
            nodes.add(new TimedRegion(item.get("timeMs").longValue(),item.get("region").isNull()?null:rectangle(item.get("region"),analysis)));
        }
        return new IgnoreRegion(0,0,0,0,nodes,null,null,analysis);
    }
'''
s=s.replace('    public static IgnoreRegion parse(String value) {',insert+'    public static IgnoreRegion parse(String value) {')
f.write_text(s,encoding='utf-8')
(p/'src/test/java/cn/videostudy/api/AnalysisRegionTest.java').write_text('''package cn.videostudy.api;
import org.junit.jupiter.api.Test;
import com.fasterxml.jackson.databind.ObjectMapper;
import static org.junit.jupiter.api.Assertions.*;
class AnalysisRegionTest {
 @Test void combinedRegionsRoundTripAndAllowFullAnalysis()throws Exception{
  var json=new ObjectMapper();var input="{\\"analysisRegion\\":{\\"x\\":0,\\"y\\":0,\\"width\\":1,\\"height\\":1},\\"ignoredRegion\\":{\\"nodes\\":[{\\"timeMs\\":0,\\"region\\":null},{\\"timeMs\\":5000,\\"region\\":{\\"x\\":0.8,\\"y\\":0.8,\\"width\\":0.1,\\"height\\":0.1}}]}}";
  assertEquals(json.readTree(input),json.readTree(json.writeValueAsString(IgnoreRegion.parse(input))));
 }
 @Test void rejectsCompleteExclusion(){
  assertThrows(IllegalArgumentException.class,()->IgnoreRegion.parse("{\\"analysisRegion\\":{\\"x\\":0.2,\\"y\\":0.2,\\"width\\":0.2,\\"height\\":0.2},\\"ignoredRegion\\":{\\"x\\":0.1,\\"y\\":0.1,\\"width\\":0.5,\\"height\\":0.5}}"));
 }
}
''',encoding='utf-8')
