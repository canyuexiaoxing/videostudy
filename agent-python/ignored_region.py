"""Normalized ignore region used only for screenshot selection and page grouping."""
import math
import numpy as np

def normalize_region(value):
    if value is None:
        return None
    if not isinstance(value,dict) or set(value) != {'x','y','width','height'}:
        raise ValueError('invalid_ignored_region')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in value.values()):
        raise ValueError('invalid_ignored_region')
    x,y,w,h=(float(value[k]) for k in ('x','y','width','height'))
    if x<0 or y<0 or x>=1 or y>=1 or w<=0 or h<=0 or x+w>1+1e-9 or y+h>1+1e-9 or w*h>.95:
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
