from pathlib import Path
root=Path(r'E:\workp\videostudy')
(root/'desktop/src/videoRegionTimeline.ts').write_text('''import { normalizeRegion } from './videoRegion'
import type { VideoRegion } from './videoRegion'
export type RegionNode = { timeMs: number; region: VideoRegion | null }
export type IgnoreSetting = VideoRegion | { nodes: RegionNode[] }
export function normalizeIgnoreSetting(value: unknown): IgnoreSetting | null {
  if (!value || typeof value !== 'object') return null
  if ('nodes' in value) {
    const raw = (value as {nodes: unknown}).nodes
    if (!Array.isArray(raw) || !raw.length || raw.length > 200 || Object.keys(value).length !== 1) return null
    const nodes: RegionNode[] = []
    for (const item of raw) {
      if (!item || typeof item !== 'object' || Object.keys(item).length !== 2 || !Number.isSafeInteger(item.timeMs) || item.timeMs < 0 || (!nodes.length ? item.timeMs !== 0 : item.timeMs <= nodes[nodes.length - 1].timeMs)) return null
      const region = item.region === null ? null : normalizeRegion(item.region)
      if (item.region !== null && (!region || region.width * region.height > .95)) return null
      nodes.push({timeMs: item.timeMs, region})
    }
    return {nodes}
  }
  const region = normalizeRegion(value)
  return region && region.width * region.height <= .95 ? region : null
}
export function regionNodes(setting: IgnoreSetting | null): RegionNode[] {
  return !setting ? [] : 'nodes' in setting ? setting.nodes : [{timeMs: 0, region: setting}]
}
export function regionAt(setting: IgnoreSetting | null, timeMs: number): VideoRegion | null {
  let region: VideoRegion | null = null
  for (const node of regionNodes(setting)) { if (node.timeMs > timeMs) break; region = node.region }
  return region
}
export function upsertRegionNode(setting: IgnoreSetting | null, timeMs: number, region: VideoRegion | null): IgnoreSetting {
  const nodes = regionNodes(setting).map(node => ({...node}))
  const time = nodes.length ? timeMs : 0
  if (!Number.isSafeInteger(time) || time < 0) throw new Error('节点时间无效')
  const index = nodes.findIndex(node => node.timeMs === time)
  if (index >= 0) nodes[index] = {timeMs: time, region}
  else nodes.push({timeMs: time, region})
  nodes.sort((a, b) => a.timeMs - b.timeMs)
  const normalized = normalizeIgnoreSetting({nodes})
  if (!normalized) throw new Error('最多保存 200 个节点，请检查区域或删除多余节点')
  return normalized
}
export function removeRegionNode(setting: IgnoreSetting | null, timeMs: number): IgnoreSetting | null {
  if (timeMs === 0) return setting
  const nodes = regionNodes(setting).filter(node => node.timeMs !== timeMs)
  return nodes.length ? {nodes} : null
}
''',encoding='utf-8')
p=root/'agent-python/ignored_region.py'
with p.open('a',encoding='utf-8') as f:
 f.write('''

def normalize_setting(value):
    """Backward-compatible static rectangle or strictly ordered timed rectangles."""
    if value is None or not isinstance(value, dict) or 'nodes' not in value:
        return normalize_region(value)
    nodes = value.get('nodes')
    if set(value) != {'nodes'} or not isinstance(nodes, list) or not 1 <= len(nodes) <= 200:
        raise ValueError('invalid_ignored_region')
    result, previous = [], -1
    for node in nodes:
        if (not isinstance(node, dict) or set(node) != {'timeMs', 'region'} or
                type(node['timeMs']) is not int or not 0 <= node['timeMs'] <= 9007199254740991 or
                node['timeMs'] <= previous or (previous == -1 and node['timeMs'] != 0)):
            raise ValueError('invalid_ignored_region')
        result.append(dict(timeMs=node['timeMs'], region=normalize_region(node['region'])))
        previous = node['timeMs']
    return {'nodes': result}


def region_at(setting, time_ms):
    if not setting or 'nodes' not in setting:
        return setting
    region = None
    for node in setting['nodes']:
        if node['timeMs'] > time_ms: break
        region = node['region']
    return region
''')
for name in ('app.py','analysis.py','visual_evidence.py'):
 p=root/'agent-python'/name;s=p.read_text(encoding='utf-8').replace('from ignored_region import normalize_region','from ignored_region import normalize_setting as normalize_region')
 p.write_text(s,encoding='utf-8')
(root/'backend-java/src/main/java/cn/videostudy/api/IgnoreRegion.java').write_text('''package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.annotation.JsonValue;
import java.util.List;
import java.util.Map;

/** Normalized fixed rectangle or piecewise-constant timeline, backward compatible on the wire. */
public record IgnoreRegion(double x, double y, double width, double height, List<TimedRegion> nodes) {
    public record TimedRegion(long timeMs, IgnoreRegion region) {
        public TimedRegion {
            if(timeMs<0||timeMs>9007199254740991L||(region!=null&&region.nodes()!=null))
                throw new IllegalArgumentException("invalid_ignored_region");
        }
    }
    public IgnoreRegion(double x,double y,double width,double height) { this(x,y,width,height,null); }
    public IgnoreRegion {
        if(nodes!=null) {
            if(x!=0||y!=0||width!=0||height!=0||nodes.isEmpty()||nodes.size()>200||nodes.getFirst().timeMs()!=0)
                throw new IllegalArgumentException("invalid_ignored_region");
            long previous=-1;
            for(var node:nodes){if(node==null||node.timeMs()<=previous)throw new IllegalArgumentException("invalid_ignored_region");previous=node.timeMs();}
            nodes=List.copyOf(nodes);
        } else {
            if (!Double.isFinite(x)||!Double.isFinite(y)||!Double.isFinite(width)||!Double.isFinite(height)
                || x<0||y<0||x>=1||y>=1||width<=0||height<=0||x+width>1+1e-9
                || y+height>1+1e-9||width*height>.95) throw new IllegalArgumentException("invalid_ignored_region");
            width=Math.min(width,1-x);height=Math.min(height,1-y);
        }
    }
    @JsonValue public Map<String,Object> jsonValue() {
        return nodes==null?Map.of("x",x,"y",y,"width",width,"height",height):Map.of("nodes",nodes);
    }
    private static IgnoreRegion rectangle(JsonNode node) {
        if(node==null||!node.isObject()||node.size()!=4)throw new IllegalArgumentException("invalid_ignored_region");
        for(var key:List.of("x","y","width","height"))if(!node.has(key)||!node.get(key).isNumber())throw new IllegalArgumentException("invalid_ignored_region");
        return new IgnoreRegion(node.get("x").doubleValue(),node.get("y").doubleValue(),node.get("width").doubleValue(),node.get("height").doubleValue());
    }
    public static IgnoreRegion parse(String value) {
        if(value==null||value.isBlank())return null;
        try {
            var parser=new ObjectMapper();
            try(var tokens=parser.createParser(value)) {
                JsonNode node=parser.readTree(tokens);
                if(tokens.nextToken()!=null||node==null||!node.isObject())throw new IllegalArgumentException("invalid_ignored_region");
                if(!node.has("nodes"))return rectangle(node);
                if(node.size()!=1||!node.get("nodes").isArray()||node.get("nodes").size()>200)throw new IllegalArgumentException("invalid_ignored_region");
                var nodes=new java.util.ArrayList<TimedRegion>();
                for(var item:node.get("nodes")) {
                    if(!item.isObject()||item.size()!=2||!item.has("timeMs")||!item.get("timeMs").isIntegralNumber()||!item.get("timeMs").canConvertToLong()||!item.has("region"))throw new IllegalArgumentException("invalid_ignored_region");
                    nodes.add(new TimedRegion(item.get("timeMs").longValue(),item.get("region").isNull()?null:rectangle(item.get("region"))));
                }
                return new IgnoreRegion(0,0,0,0,nodes);
            }
        } catch(Exception error){throw new IllegalArgumentException("invalid_ignored_region",error);}
    }
}
''',encoding='utf-8')
