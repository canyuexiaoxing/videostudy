from pathlib import Path
p=Path('E:/workp/videostudy/agent-python/slide_grouping.py')
s=p.read_text(encoding='utf-8').replace('    if ignore_region:\n        filtered=[]', '    dimensions = {}\n    if ignore_region:\n        filtered=[]').replace('            height,width=original.shape\n            filtered.append', '            height,width=original.shape\n            dimensions[frame["frameTimeMs"]]=(width,height)\n            filtered.append')
old='''            boundary = _boundary(anchor, previous, current, images[anchor["frameTimeMs"]],
                                 images[previous["frameTimeMs"]], current_image, comparison_mask)'''
new='''            # Compare OCR under the same exclusions as pixels. Moving the mask
            # must not look like disappearing/replaced lesson text.
            compare_anchor, compare_previous, compare_current = anchor, previous, current
            if ignore_region:
                regions = [region_at(ignore_region,item["frameTimeMs"]) for item in (anchor,previous,current)]
                def common_ocr(item):
                    result = item
                    for region in regions:
                        result = grouping_frame(result,region,*dimensions[item["frameTimeMs"]])
                    return result
                compare_anchor, compare_previous, compare_current = map(common_ocr,(anchor,previous,current))
            boundary = _boundary(compare_anchor, compare_previous, compare_current, images[anchor["frameTimeMs"]],
                                 images[previous["frameTimeMs"]], current_image, comparison_mask)'''
assert old in s;s=s.replace(old,new).replace('for block in previous.get("ocrBlocks", [])','for block in compare_previous.get("ocrBlocks", [])').replace('for block in current.get("ocrBlocks", [])','for block in compare_current.get("ocrBlocks", [])')
p.write_text(s,encoding='utf-8')
