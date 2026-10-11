from pathlib import Path
import json
root=Path(r'E:\workp\videostudy')
p=root/'desktop/src/videoRegionTimeline.ts';s=p.read_text().replace("from './videoRegion'","from './videoRegion.ts'");p.write_text(s,encoding='utf-8')
p=root/'desktop/tsconfig.json';s=json.loads(p.read_text());s['compilerOptions']['allowImportingTsExtensions']=True;p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=root/'agent-python/visual_evidence.py';s=p.read_text(encoding='utf-8')
start=s.index('    if ignore_region:\n        r = ignore_region');end=s.index('    process = subprocess.Popen',start)
s=s[:start]+'''    if ignore_region:
        nodes = ignore_region['nodes'] if 'nodes' in ignore_region else [{'timeMs': 0, 'region': ignore_region}]
        geometry = f"scale={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:force_original_aspect_ratio=decrease,pad={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=gray"
        boxes = []
        for index, node in enumerate(nodes):
            r = node['region']
            if r is None: continue
            enabled = f"gte(t,{node['timeMs']/1000})"
            if index + 1 < len(nodes): enabled += f"*lt(t,{nodes[index+1]['timeMs']/1000})"
            boxes.append(f"drawbox=x=iw*{r['x']}:y=ih*{r['y']}:w=iw*{r['width']}:h=ih*{r['height']}:color=black:t=fill:enable='{enabled}'")
        mask_filters = 'format=gray,lut=y=255,' + (','.join(boxes) + ',' if boxes else '') + geometry
        filters = (f"[0:v]fps=1/{sample_seconds},split=2[v][m];[v]{geometry}[p];"
                   f"[m]{mask_filters}[mask];[p][mask]vstack,format=gray[out]")
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                   "-filter_complex", filters, "-map", "[out]", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
        read_bytes = FRAME_BYTES * 2
''' + s[end:]
s=s.replace('    first_frame = None\n    index = 0','''    first_frame = None
    previous_mask = first_mask = last_chosen_mask = None
    def visible_difference(left, right, left_mask, right_mask):
        difference = cv2.absdiff(left, right) > 25
        if left_mask is None: return float(np.mean(difference))
        visible = left_mask & right_mask
        # No common visible area is not proof of sameness: conservatively retain evidence.
        return float(np.mean(difference[visible])) if visible.any() else 1.0
    index = 0''')
s=s.replace('                first_frame = frame.copy()','                first_frame = frame.copy()\n                first_mask = mask.copy() if mask is not None else None')
s=s.replace('float(np.mean((cv2.absdiff(previous, frame) > 25)[mask] if mask is not None else cv2.absdiff(previous, frame) > 25))','visible_difference(previous, frame, previous_mask, mask)')
s=s.replace('float(np.mean((cv2.absdiff(baseline, previous) > 25)[mask] if mask is not None else cv2.absdiff(baseline, previous) > 25))','visible_difference(baseline, previous, last_chosen_mask if last_chosen_frame is not None else first_mask, previous_mask)')
s=s.replace('                    last_chosen_frame = previous.copy()','                    last_chosen_frame = previous.copy()\n                    last_chosen_mask = previous_mask.copy() if previous_mask is not None else None',1)
s=s.replace('                        last_chosen_frame = previous.copy()','                        last_chosen_frame = previous.copy()\n                        last_chosen_mask = previous_mask.copy() if previous_mask is not None else None')
s=s.replace('            previous = frame.copy()','            previous = frame.copy()\n            previous_mask = mask.copy() if mask is not None else None')
p.write_text(s,encoding='utf-8')
p=root/'agent-python/slide_grouping.py';s=p.read_text(encoding='utf-8')
s=s.replace('from ignored_region import normalize_region, valid_mask, grouping_frame','from ignored_region import normalize_setting as normalize_region, region_at, valid_mask, grouping_frame')
s=s.replace('''    difference = cv2.absdiff(left, right) > 25
    direct''','''    if mask is not None and not mask.any(): return 1.0
    difference = cv2.absdiff(left, right) > 25
    direct''')
s=s.replace('''        image = images[item["frameTimeMs"]]
        return''','''        image = images[item["frameTimeMs"]]
        visible = mask.get(item["frameTimeMs"]) if isinstance(mask, dict) else mask
        return''')
s=s.replace('mask.astype(np.uint8)', 'visible.astype(np.uint8)',1).replace('if mask is not None else cv2.Laplacian(image, cv2.CV_64F)).var()', 'if visible is not None else cv2.Laplacian(image, cv2.CV_64F)).var()',1)
s=s.replace('    mask = valid_mask(320,180,ignore_region) if ignore_region else None','    masks = {time: valid_mask(320,180,region_at(ignore_region,time)) for time in times} if ignore_region else None')
s=s.replace('grouping_frame(frame,ignore_region,width,height)','grouping_frame(frame,region_at(ignore_region,frame["frameTimeMs"]),width,height)')
s=s.replace('        current_image = images[time_ms]','        current_image = images[time_ms]\n        mask = masks[time_ms] if masks is not None else None')
s=s.replace('len(pages) + 1, mask)', 'len(pages) + 1, masks)')
s=s.replace('''            boundary = _boundary(anchor, previous, current, images[anchor["frameTimeMs"]],
                                 images[previous["frameTimeMs"]], current_image, mask)''','''            comparison_mask = mask & masks[previous["frameTimeMs"]] & masks[anchor["frameTimeMs"]] if masks is not None else None
            boundary = _boundary(anchor, previous, current, images[anchor["frameTimeMs"]],
                                 images[previous["frameTimeMs"]], current_image, comparison_mask)''')
p.write_text(s,encoding='utf-8')
