package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.annotation.JsonValue;
import java.util.List;
import java.util.Map;

/** Normalized fixed rectangle or piecewise-constant timeline, backward compatible on the wire. */
public record IgnoreRegion(double x, double y, double width, double height, List<TimedRegion> nodes, IgnoreRegion analysisRegion, IgnoreRegion ignoredRegion, boolean allowFull) {
    public record TimedRegion(long timeMs, IgnoreRegion region) {
        public TimedRegion {
            if(timeMs<0||timeMs>9007199254740991L||(region!=null&&(region.nodes()!=null||region.analysisRegion()!=null||region.ignoredRegion()!=null)))
                throw new IllegalArgumentException("invalid_ignored_region");
        }
    }
    public IgnoreRegion(double x,double y,double width,double height) { this(x,y,width,height,null); }
    public IgnoreRegion(double x,double y,double width,double height,List<TimedRegion> nodes){this(x,y,width,height,nodes,null,null,false);}
    public IgnoreRegion {
        if(analysisRegion!=null||ignoredRegion!=null){
            if(x!=0||y!=0||width!=0||height!=0||nodes!=null||allowFull)throw new IllegalArgumentException("invalid_media_regions");
            for(var child:new IgnoreRegion[]{analysisRegion,ignoredRegion})if(child!=null&&(child.analysisRegion()!=null||child.ignoredRegion()!=null))throw new IllegalArgumentException("invalid_media_regions");
            var times=new java.util.TreeSet<Long>();times.add(0L);
            for(var child:new IgnoreRegion[]{analysisRegion,ignoredRegion})if(child!=null&&child.nodes()!=null)for(var node:child.nodes())times.add(node.timeMs());
            for(var time:times){var a=at(analysisRegion,time);var b=at(ignoredRegion,time);if(a!=null&&b!=null&&b.x()<=a.x()&&b.y()<=a.y()&&b.x()+b.width()>=a.x()+a.width()&&b.y()+b.height()>=a.y()+a.height())throw new IllegalArgumentException("analysis_region_fully_ignored");}
        } else if(nodes!=null) {
            if(x!=0||y!=0||width!=0||height!=0||nodes.isEmpty()||nodes.size()>200||nodes.getFirst()==null||nodes.getFirst().timeMs()!=0)
                throw new IllegalArgumentException("invalid_ignored_region");
            long previous=-1;
            for(var node:nodes){if(node==null||node.timeMs()<=previous)throw new IllegalArgumentException("invalid_ignored_region");previous=node.timeMs();}
            nodes=List.copyOf(nodes);
        } else {
            if (!Double.isFinite(x)||!Double.isFinite(y)||!Double.isFinite(width)||!Double.isFinite(height)
                || x<0||y<0||x>=1||y>=1||width<=0||height<=0||x+width>1+1e-9
                || y+height>1+1e-9||(!allowFull&&width*height>.95)) throw new IllegalArgumentException("invalid_ignored_region");
            width=Math.min(width,1-x);height=Math.min(height,1-y);
        }
    }
    @JsonValue public Map<String,Object> jsonValue() {
        if(analysisRegion!=null||ignoredRegion!=null){var result=new java.util.LinkedHashMap<String,Object>();result.put("analysisRegion",analysisRegion);result.put("ignoredRegion",ignoredRegion);return result;}
        return nodes==null?Map.of("x",x,"y",y,"width",width,"height",height):Map.of("nodes",nodes);
    }
    private static IgnoreRegion rectangle(JsonNode node,boolean analysis) {
        if(node==null||!node.isObject()||node.size()!=4)throw new IllegalArgumentException("invalid_ignored_region");
        for(var key:List.of("x","y","width","height"))if(!node.has(key)||!node.get(key).isNumber())throw new IllegalArgumentException("invalid_ignored_region");
        return new IgnoreRegion(node.get("x").doubleValue(),node.get("y").doubleValue(),node.get("width").doubleValue(),node.get("height").doubleValue(),null,null,null,analysis);
    }
    private static IgnoreRegion at(IgnoreRegion value,long time){if(value==null||value.nodes()==null)return value;IgnoreRegion region=null;for(var node:value.nodes()){if(node.timeMs()>time)break;region=node.region();}return region;}
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
    public static IgnoreRegion parse(String value) {
        if(value==null||value.isBlank())return null;
        try {
            var parser=new ObjectMapper();
            try(var tokens=parser.createParser(value)) {
                JsonNode node=parser.readTree(tokens);
                if(tokens.nextToken()!=null||node==null||!node.isObject())throw new IllegalArgumentException("invalid_ignored_region");
                return fromNode(node,false);

            }
        } catch(Exception error){throw new IllegalArgumentException("invalid_ignored_region",error);}
    }
}
