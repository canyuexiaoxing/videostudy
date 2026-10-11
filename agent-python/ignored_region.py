"""Normalized ignore region used only for screenshot selection and page grouping."""
import math
import numpy as np

def normalize_region(value, *, allow_full=False):
    if value is None:
        return None
    if not isinstance(value,dict) or set(value) != {'x','y','width','height'}:
        raise ValueError('invalid_ignored_region')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in value.values()):
        raise ValueError('invalid_ignored_region')
    x,y,w,h=(float(value[k]) for k in ('x','y','width','height'))
    if x<0 or y<0 or x>=1 or y>=1 or w<=0 or h<=0 or x+w>1+1e-9 or y+h>1+1e-9 or (not allow_full and w*h>.95):
        raise ValueError('invalid_ignored_region')
    return dict(x=x,y=y,width=min(w,1-x),height=min(h,1-y))

def valid_mask(width,height,region):
    region=normalize_region(region)
    mask=np.ones((height,width),dtype=bool)
    if region:
        x,y,w,h=(region[k] for k in ('x','y','width','height'))
        mask[math.floor(y*height):math.ceil((y+h)*height),math.floor(x*width):math.ceil((x+w)*width)]=False
    if not mask.any():
        raise ValueError('ignored_region_leaves_no_visible_pixels')
    return mask

def grouping_frame(frame,region,width,height):
    """Filter grouping evidence without editing raw OCR; unknown positions are retained."""
    if region is None:
        return frame
    x,y,w,h=(region[k] for k in ('x','y','width','height'))
    left,top,right,bottom=x*width,y*height,(x+w)*width,(y+h)*height
    blocks=[]
    for index,block in enumerate(frame.get('ocrBlocks',[])):
        polygon=block.get('polygon')
        try:
            points=np.asarray(polygon,dtype=float)
            if points.ndim==2 and points.shape[1]==2 and len(points)>=2 and np.isfinite(points).all():
                bx,by=points.min(axis=0);ex,ey=points.max(axis=0)
                area=(ex-bx)*(ey-by)
                overlap=max(0,min(ex,right)-max(bx,left))*max(0,min(ey,bottom)-max(by,top))
                if area>0 and overlap/area>=.5:
                    continue
        except (TypeError,ValueError):
            pass
        blocks.append(dict(block,_sourceBlockIndex=index))
    return dict(frame,ocrBlocks=blocks)


def normalize_setting(value, *, analysis=False):
    """Backward-compatible static rectangle or strictly ordered timed rectangles."""
    if isinstance(value,dict) and ('analysisRegion' in value or 'ignoredRegion' in value):
        if analysis or set(value)!={'analysisRegion','ignoredRegion'}:raise ValueError('invalid_media_regions')
        for child in value.values():
            if isinstance(child,dict) and ('analysisRegion' in child or 'ignoredRegion' in child):raise ValueError('invalid_media_regions')
        result={'analysisRegion':normalize_setting(value['analysisRegion'],analysis=True),'ignoredRegion':normalize_setting(value['ignoredRegion'])}
        times={0}
        for child in result.values():
            if child and 'nodes' in child:times.update(node['timeMs'] for node in child['nodes'])
        for time in times:
            included,excluded=active_regions(result,time)
            if included and excluded and excluded['x']<=included['x'] and excluded['y']<=included['y'] and excluded['x']+excluded['width']>=included['x']+included['width'] and excluded['y']+excluded['height']>=included['y']+included['height']:
                raise ValueError('analysis_region_fully_ignored')
        return result
    if value is None or not isinstance(value, dict) or 'nodes' not in value:
        return normalize_region(value,allow_full=analysis)
    nodes = value.get('nodes')
    if set(value) != {'nodes'} or not isinstance(nodes, list) or not 1 <= len(nodes) <= 200:
        raise ValueError('invalid_ignored_region')
    result, previous = [], -1
    for node in nodes:
        if (not isinstance(node, dict) or set(node) != {'timeMs', 'region'} or
                type(node['timeMs']) is not int or not 0 <= node['timeMs'] <= 9007199254740991 or
                node['timeMs'] <= previous or (previous == -1 and node['timeMs'] != 0)):
            raise ValueError('invalid_ignored_region')
        result.append(dict(timeMs=node['timeMs'], region=normalize_region(node['region'],allow_full=analysis)))
        previous = node['timeMs']
    return {'nodes': result}


def region_at(setting, time_ms):
    if setting and 'analysisRegion' in setting:setting=setting['ignoredRegion']
    if not setting or 'nodes' not in setting:
        return setting
    region = None
    for node in setting['nodes']:
        if node['timeMs'] > time_ms: break
        region = node['region']
    return region


def active_regions(setting,time_ms):
    if setting and 'analysisRegion' in setting:
        return region_at(setting['analysisRegion'],time_ms),region_at(setting['ignoredRegion'],time_ms)
    return None,region_at(setting,time_ms)

def effective_mask(width,height,setting,time_ms):
    included,excluded=active_regions(setting,time_ms)
    mask=valid_mask(width,height,excluded)
    if included:
        allowed=np.zeros((height,width),dtype=bool)
        x,y,w,h=(included[k] for k in ('x','y','width','height'))
        allowed[math.floor(y*height):math.ceil((y+h)*height),math.floor(x*width):math.ceil((x+w)*width)]=True
        mask &= allowed
    if not mask.any():raise ValueError('analysis_region_fully_ignored')
    return mask

def prepare_image(image,setting,time_ms):
    result=image.copy();mask=effective_mask(image.shape[1],image.shape[0],setting,time_ms)
    result[~mask]=255
    return result

def filter_frame(frame,setting,time_ms,width,height):
    if not setting:return frame
    included,_=active_regions(setting,time_ms)
    mask=effective_mask(width,height,setting,time_ms)
    blocks=[]
    for index,block in enumerate(frame.get('ocrBlocks',[])):
        try:
            points=np.asarray(block.get('polygon'),dtype=float)
            if points.ndim!=2 or points.shape[1]!=2 or len(points)<2 or not np.isfinite(points).all():raise ValueError()
            low=points.min(axis=0);high=points.max(axis=0)
            left=max(0,math.floor(low[0]));top=max(0,math.floor(low[1]));right=min(width,math.ceil(high[0]));bottom=min(height,math.ceil(high[1]))
            area=(right-left)*(bottom-top)
            if area<=0 or float(mask[top:bottom,left:right].mean())<=.5:continue
        except (TypeError,ValueError):
            if included:continue
        blocks.append(dict(block,_sourceBlockIndex=block.get('_sourceBlockIndex',index)))
    return dict(frame,ocrBlocks=blocks)
