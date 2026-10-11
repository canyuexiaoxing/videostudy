from pathlib import Path
p=Path('E:/workp/videostudy/agent-python')
f=p/'ignored_region.py';s=f.read_text(encoding='utf-8').replace('def normalize_region(value):','def normalize_region(value, *, allow_full=False):').replace('or w*h>.95:', 'or (not allow_full and w*h>.95):')
s=s.replace('def normalize_setting(value):','def normalize_setting(value, *, analysis=False):').replace("    if value is None or not isinstance(value, dict) or 'nodes' not in value:\n        return normalize_region(value)", '''    if isinstance(value,dict) and ('analysisRegion' in value or 'ignoredRegion' in value):
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
        return normalize_region(value,allow_full=analysis)''').replace("region=normalize_region(node['region'])", "region=normalize_region(node['region'],allow_full=analysis)")
s=s.replace('def region_at(setting, time_ms):\n', "def region_at(setting, time_ms):\n    if setting and 'analysisRegion' in setting:setting=setting['ignoredRegion']\n")
s+='''

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
'''
f.write_text(s,encoding='utf-8')
f=p/'visual_evidence.py';s=f.read_text(encoding='utf-8').replace('from ignored_region import normalize_setting as normalize_region', 'from ignored_region import normalize_setting as normalize_region,prepare_image,active_regions')
s=s.replace("        nodes = ignore_region['nodes'] if 'nodes' in ignore_region else [{'timeMs': 0, 'region': ignore_region}]", '''        included = ignore_region.get('analysisRegion') if 'analysisRegion' in ignore_region else None
        excluded = ignore_region.get('ignoredRegion') if 'analysisRegion' in ignore_region else ignore_region
        def timed_nodes(value):return value['nodes'] if value and 'nodes' in value else [{'timeMs':0,'region':value}]
        groups=[(timed_nodes(included),True),(timed_nodes(excluded),False)]''')
start=s.index('        for index, node in enumerate(nodes):');end=s.index("        mask_filters =",start)
s=s[:start]+'''        for nodes,is_include in groups:
            for index,node in enumerate(nodes):
                r=node['region']
                if r is None:continue
                enabled=f"gte(t,{node['timeMs']/1000})"
                if index+1<len(nodes):enabled+=f"*lt(t,{nodes[index+1]['timeMs']/1000})"
                if is_include:boxes.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='{enabled}'")
                color='white' if is_include else 'black'
                boxes.append(f"drawbox=x=iw*{r['x']}:y=ih*{r['y']}:w=iw*{r['width']}:h=ih*{r['height']}:color={color}:t=fill:enable='{enabled}'")
''' +s[end:]
pos=s.index('def analyze_visuals(')
s=s[:pos]+'''def recognize_in_region(frame,setting,time_ms,recognize):
    # Keep legacy full-frame OCR unchanged; analysis regions opt into masked OCR.
    if setting and 'analysisRegion' in setting:
        return recognize(prepare_image(frame,setting,time_ms))
    return recognize(frame)


'''+s[pos:]
s=s.replace("checkpoint.run(f'ocrFrame:{time_ms}', {}, lambda: recognize(frame)) if checkpoint else recognize(frame)", "checkpoint.run(f'ocrFrame:{time_ms}', {'regions':ignore_region}, lambda: recognize_in_region(frame,ignore_region,time_ms,recognize)) if checkpoint else recognize_in_region(frame,ignore_region,time_ms,recognize)")
s=s.replace("checkpoint.run(f'ocrFrame:{request[\"timeMs\"]}', {}, lambda: _recognize(frame)) if checkpoint else _recognize(frame)", "checkpoint.run(f'ocrFrame:{request[\"timeMs\"]}', {'regions':ignore_region}, lambda: recognize_in_region(frame,ignore_region,request['timeMs'],_recognize)) if checkpoint else recognize_in_region(frame,ignore_region,request['timeMs'],_recognize)")
s=s.replace("checkpoint.run(f'ocrFrame:{time_ms}', {}, lambda: _recognize(frame)) if checkpoint else _recognize(frame)", "checkpoint.run(f'ocrFrame:{time_ms}', {'regions':ignore_region}, lambda: recognize_in_region(frame,ignore_region,time_ms,_recognize)) if checkpoint else recognize_in_region(frame,ignore_region,time_ms,_recognize)")
f.write_text(s,encoding='utf-8')
f=p/'slide_grouping.py';s=f.read_text(encoding='utf-8').replace('valid_mask, grouping_frame','valid_mask, grouping_frame, effective_mask, filter_frame')
s=s.replace('valid_mask(320,180,region_at(ignore_region,time))','effective_mask(320,180,ignore_region,time)').replace('grouping_frame(frame,region_at(ignore_region,frame["frameTimeMs"]),width,height)','filter_frame(frame,ignore_region,frame["frameTimeMs"],width,height)')
s=s.replace('grouping_frame(common_anchor,region_at(ignore_region,item["frameTimeMs"]),*dimensions[anchor_frame["frameTimeMs"]])','filter_frame(common_anchor,ignore_region,item["frameTimeMs"],*dimensions[anchor_frame["frameTimeMs"]])')
s=s.replace('regions = [region_at(ignore_region,item["frameTimeMs"]) for item in (anchor,previous,current)]', 'regions = [item["frameTimeMs"] for item in (anchor,previous,current)]').replace('result = grouping_frame(result,region,*dimensions[item["frameTimeMs"]])','result = filter_frame(result,ignore_region,region,*dimensions[item["frameTimeMs"]])')
f.write_text(s,encoding='utf-8')
f=p/'page_understanding.py';s=f.read_text(encoding='utf-8')
s=s.replace('encoded = base64.b64encode(path.read_bytes()).decode("ascii")', '''if context.get('_visualRegions'):
            import cv2
            from ignored_region import prepare_image
            original=cv2.imread(str(path))
            if original is None:raise ValueError('unreadable_region_frame')
            ok,image=cv2.imencode('.jpg',prepare_image(original,context['_visualRegions'],frame_time))
            if not ok:raise ValueError('unreadable_region_frame')
            encoded=base64.b64encode(image).decode('ascii')
        else:encoded = base64.b64encode(path.read_bytes()).decode("ascii")''')
# Attach settings to pages, and propagate into the request context at its builder.
s=s.replace('    if mode == "ocr_only":', "    if page.get('_visualRegions'):context['_visualRegions']=page['_visualRegions']\n    if mode == \"ocr_only\":",1)
# Settings are transport metadata, not instructions or model-readable evidence.
s=s.replace('compact_payload(context)', "compact_payload({k:v for k,v in context.items() if k!='_visualRegions'})")
f.write_text(s,encoding='utf-8')
f=p/'analysis.py';s=f.read_text(encoding='utf-8').replace('                def understand(page):\n', "                def understand(page):\n                    if ignore_region:page=dict(page,_visualRegions=ignore_region)\n")
f.write_text(s,encoding='utf-8')
