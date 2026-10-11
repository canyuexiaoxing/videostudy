from pathlib import Path
root=Path('E:/workp/videostudy')
def edit(name,changes):
    path=root/name
    text=path.read_text(encoding='utf-8')
    for before,after in changes:
        assert before in text,(name,before)
        text=text.replace(before,after)
    path.write_text(text,encoding='utf-8')
(root/'agent-python/ignored_region.py').write_text('''"""Normalized ignore region used only for screenshot selection and page grouping."""
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
    if x<0 or y<0 or w<=0 or h<=0 or x+w>1+1e-9 or y+h>1+1e-9 or w*h>.95:
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
''',encoding='utf-8')
edit('agent-python/visual_evidence.py',[
('from checkpoints import Checkpoints','from checkpoints import Checkpoints\nfrom ignored_region import normalize_region'),
('sample_seconds: int = SAMPLE_SECONDS) -> list[int]:','sample_seconds: int = SAMPLE_SECONDS, ignore_region: dict | None = None) -> list[int]:'),
('    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)', '''    ignore_region = normalize_region(ignore_region)
    read_bytes = FRAME_BYTES
    mask = None
    if ignore_region:
        r = ignore_region
        geometry = f"scale={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:force_original_aspect_ratio=decrease,pad={PREVIEW_WIDTH}:{PREVIEW_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=gray"
        filters = (f"[0:v]fps=1/{sample_seconds},split=2[v][m];[v]{geometry}[p];"
                   f"[m]format=gray,lut=y=255,drawbox=x=iw*{r['x']}:y=ih*{r['y']}:w=iw*{r['width']}:h=ih*{r['height']}:color=black:t=fill,{geometry}[mask];"
                   "[p][mask]vstack,format=gray[out]")
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                   "-filter_complex", filters, "-map", "[out]", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
        read_bytes = FRAME_BYTES * 2
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)'''),
('process.stdout.read(FRAME_BYTES)','process.stdout.read(read_bytes)'),
('len(frame_bytes) != FRAME_BYTES','len(frame_bytes) != read_bytes'),
('frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(PREVIEW_HEIGHT, PREVIEW_WIDTH)', '''frame = np.frombuffer(frame_bytes[:FRAME_BYTES], dtype=np.uint8).reshape(PREVIEW_HEIGHT, PREVIEW_WIDTH)
            if ignore_region:
                mask = np.frombuffer(frame_bytes[FRAME_BYTES:], dtype=np.uint8).reshape(PREVIEW_HEIGHT, PREVIEW_WIDTH) >= 254
                if not mask.any():
                    raise ValueError("ignored_region_leaves_no_visible_pixels")'''),
('np.mean(cv2.absdiff(previous, frame) > 25)','np.mean((cv2.absdiff(previous, frame) > 25)[mask] if mask is not None else cv2.absdiff(previous, frame) > 25)'),
('np.mean(cv2.absdiff(baseline, previous) > 25)','np.mean((cv2.absdiff(baseline, previous) > 25)[mask] if mask is not None else cv2.absdiff(baseline, previous) > 25)'),
('sample_seconds: int = SAMPLE_SECONDS) -> list[dict]:','sample_seconds: int = SAMPLE_SECONDS, ignore_region: dict | None = None) -> list[dict]:'),
('_candidate_times(path, page_change_fraction, sample_seconds)','_candidate_times(path, page_change_fraction, sample_seconds, ignore_region)'),
('    sample_seconds = SAMPLE_SECONDS\n    checkpoint', '    sample_seconds = SAMPLE_SECONDS\n    ignore_region = None\n    checkpoint'),
('sample_seconds = request["sampleSeconds"]','sample_seconds = request["sampleSeconds"]\n                    ignore_region = normalize_region(request.get("ignoredRegion"))'),
('page_change_fraction=page_change_fraction, sample_seconds=sample_seconds)','page_change_fraction=page_change_fraction, sample_seconds=sample_seconds, ignore_region=ignore_region)'),
('page_change_fraction: float = PAGE_CHANGE_FRACTION, sample_seconds: int = SAMPLE_SECONDS):','page_change_fraction: float = PAGE_CHANGE_FRACTION, sample_seconds: int = SAMPLE_SECONDS,\n                 ignore_region: dict | None = None):'),
('        global _shared_connection, _shared_process','        ignore_region = normalize_region(ignore_region)\n        global _shared_connection, _shared_process'),
('pageChangeFraction=page_change_fraction, sampleSeconds=sample_seconds)','pageChangeFraction=page_change_fraction, sampleSeconds=sample_seconds, ignoredRegion=ignore_region)'),
])
edit('agent-python/slide_grouping.py',[
('import numpy as np','import numpy as np\nfrom ignored_region import normalize_region, valid_mask, grouping_frame'),
('def _difference(left: np.ndarray, right: np.ndarray) -> float:', 'def _difference(left: np.ndarray, right: np.ndarray, mask=None) -> float:'),
('    direct = float(np.mean(cv2.absdiff(left, right) > 25))','    difference = cv2.absdiff(left, right) > 25\n    direct = float(np.mean(difference[mask] if mask is not None else difference))'),
('left.std() < 8 or right.std() < 8','(left[mask] if mask is not None else left).std() < 8 or (right[mask] if mask is not None else right).std() < 8'),
('cv2.phaseCorrelate(left.astype(np.float32), right.astype(np.float32))','cv2.phaseCorrelate(np.where(mask, left, 0).astype(np.float32) if mask is not None else left.astype(np.float32), np.where(mask, right, 0).astype(np.float32) if mask is not None else right.astype(np.float32))'),
('    # Ignore the narrow border introduced by alignment.','''    if mask is not None:
        shifted_mask = cv2.warpAffine(mask.astype(np.uint8), np.float32([[1, 0, -dx], [0, 1, -dy]]),
                                     (right.shape[1], right.shape[0]), flags=cv2.INTER_NEAREST).astype(bool)
        valid = (mask & shifted_mask)[6:-6, 6:-6]
        if not valid.any():
            return direct
        return min(direct, float(np.mean((cv2.absdiff(left[6:-6,6:-6], aligned[6:-6,6:-6]) > 25)[valid])))
    # Ignore the narrow border introduced by alignment.'''),
('def _blank(frame: dict, image: np.ndarray) -> bool:', 'def _blank(frame: dict, image: np.ndarray, mask=None) -> bool:\n    image = image[mask] if mask is not None else image'),
('current_image: np.ndarray) -> str:','current_image: np.ndarray, mask=None) -> str:'),
('_difference(previous_image, current_image)','_difference(previous_image, current_image, mask)'),
('_difference(anchor_image, current_image)','_difference(anchor_image, current_image, mask)'),
('reason: str, page_index: int) -> dict:', 'reason: str, page_index: int, mask=None) -> dict:'),
('float(cv2.Laplacian(image, cv2.CV_64F).var())','float((cv2.Laplacian(image, cv2.CV_64F)[cv2.erode(mask.astype(np.uint8), np.ones((3,3), np.uint8)).astype(bool)] if mask is not None else cv2.Laplacian(image, cv2.CV_64F)).var())'),
('"sourceBlockIndex": index','"sourceBlockIndex": block.get("_sourceBlockIndex", index)'),
('ask_json: Callable[[dict], dict] | None = None) -> tuple','ask_json: Callable[[dict], dict] | None = None, ignore_region: dict | None = None) -> tuple'),
('    images = {time: _preview(keyframe_dir / f"{time}.jpg") for time in times}', '''    ignore_region = normalize_region(ignore_region)
    mask = valid_mask(320,180,ignore_region) if ignore_region else None
    images = {time: _preview(keyframe_dir / f"{time}.jpg") for time in times}
    if ignore_region:
        filtered=[]
        for frame in frames:
            original=cv2.imread(str(keyframe_dir / f"{frame['frameTimeMs']}.jpg"),cv2.IMREAD_GRAYSCALE)
            height,width=original.shape
            filtered.append(grouping_frame(frame,ignore_region,width,height))
        frames=filtered'''),
('_blank(current, current_image)','_blank(current, current_image, mask)'),
('decision, reason, len(pages) + 1)','decision, reason, len(pages) + 1, mask)'),
('images[previous["frameTimeMs"]], current_image)','images[previous["frameTimeMs"]], current_image, mask)'),
])
edit('agent-python/analysis.py',[
('from checkpoints import Checkpoints','from checkpoints import Checkpoints\nfrom ignored_region import normalize_region'),
('subtitle_callback_token: str | None = None, coarse_sample_seconds: int = 2) -> dict:','subtitle_callback_token: str | None = None, coarse_sample_seconds: int = 2,\n                 ignore_region: dict | None = None) -> dict:\n    ignore_region = normalize_region(ignore_region)'),
("'ocr': OCR_MODEL_ID, 'ocrDevice'", "'ignoredRegion': ignore_region, 'ocr': OCR_MODEL_ID, 'ocrDevice'"),
('sample_seconds=coarse_sample_seconds) as visual_worker:','sample_seconds=coarse_sample_seconds, **({"ignore_region": ignore_region} if ignore_region else {})) as visual_worker:'),
("lambda: group_pages(visuals, keyframe_dir, transcript['segments']))", "lambda: group_pages(visuals, keyframe_dir, transcript['segments'], **({'ignore_region': ignore_region} if ignore_region else {})))"),
])
edit('agent-python/app.py',[
('from pydantic import BaseModel','from pydantic import BaseModel, field_validator\nfrom ignored_region import normalize_region'),
('    subtitleCallbackToken: str | None = None','''    subtitleCallbackToken: str | None = None
    ignoredRegion: dict | None = None

    @field_validator('ignoredRegion', mode='before')
    @classmethod
    def validate_region(cls, value):
        return normalize_region(value)'''),
('coarse_sample_seconds=request.coarseSampleSeconds)','coarse_sample_seconds=request.coarseSampleSeconds, **({"ignore_region": request.ignoredRegion} if request.ignoredRegion else {}))'),
])
for name in ['agent-python/Dockerfile','agent-python/Dockerfile.gpu']:
    edit(name,[('visual_evidence.py','visual_evidence.py ignored_region.py')])
