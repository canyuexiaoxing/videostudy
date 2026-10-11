from pathlib import Path
p=Path(r'E:\workp\videostudy\agent-python\slide_grouping.py')
s=p.read_text(encoding='utf-8').replace('cv2.warpAffine(visible.astype(np.uint8)', 'cv2.warpAffine(mask.astype(np.uint8)').replace('cv2.erode(mask.astype(np.uint8)', 'cv2.erode(visible.astype(np.uint8)')
p.write_text(s,encoding='utf-8')
