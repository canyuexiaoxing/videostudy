"""Direct synthesis from every final representative image and effective speech."""
from copy import deepcopy
from pathlib import Path
from concurrent.futures import CancelledError
import hashlib
import json
import os
import re

import course_mind_map as course
from ignored_region import normalize_setting, filter_frame

PROMPT_VERSION = 'whole-course-group-evidence-direct-v12'
INSTRUCTIONS = course.INSTRUCTIONS + '''
DIRECT MODE: There are no prior candidates or group analyses. Read ALL attached
final representative original images, page context/OCR and the full effective
transcript. Organize the entire course once. candidateIds must be []. Keep every
independent formula/rule; give conditions, symbols, steps, pitfalls and
self-corrections as cited details. Distinguish specific questions from general
knowledge. Every example is a separate grounded question, with all solution
evidence cited. Shared subject/formula never proves question identity. Only
merge a continued question when the actual matching stem/givens/numbering prove
it. Never omit images or split this whole-course request into batches.
'''


def clean_segments(segments):
    """Drop only complete, unmistakable filler/chatter utterances locally.

    Do not edit clauses: negation, conditions, corrections and timestamps survive.
    """
    filler = re.compile(r'^(?:嗯+|呃+|啊+|额+|uh+|um+|谢谢大家|感谢观看|thank you for watching)[\s，。！？,.!?]*$', re.I)
    result = []
    identities = set()
    for segment in segments:
        if (not isinstance(segment, dict) or not isinstance(segment.get('id'), str) or not segment['id']
            or type(segment.get('startMs')) is not int or type(segment.get('endMs')) is not int
            or segment['startMs'] < 0 or segment['endMs'] < segment['startMs']
            or not isinstance(segment.get('text'), str) or not segment['text'].strip()):
            raise ValueError('invalid direct transcript evidence')
        if segment['id'] in identities:
            raise ValueError('duplicate direct transcript source ID')
        identities.add(segment['id'])
        item = deepcopy(segment)
        if not filler.fullmatch(item['text'].strip()):
            result.append(item)
    return result


def _prepare(segments, pages, visuals, root, ignore_region):
    speech = clean_segments(segments)
    setting = normalize_setting(ignore_region)
    frames = {v['frameTimeMs']: v for v in visuals if isinstance(v, dict) and type(v.get('frameTimeMs')) is int}
    times, context, regions = set(), [], {}
    import cv2
    for page in pages:
        reps = page.get('representativeFrameTimesMs')
        if not isinstance(reps, list) or not reps:
            raise ValueError('direct final group has no representative image')
        page_setting = normalize_setting(setting or page.get('_visualRegions'))
        ocr = []
        for ms in reps:
            if type(ms) is not int or ms < 0:
                raise ValueError('invalid direct representative timestamp')
            if ms not in frames:raise ValueError(f'direct representative has no visual evidence metadata: frame_{ms}')
            path = root / f'{ms}.jpg'
            image = cv2.imread(str(path)) if path.is_file() else None
            if image is None:
                raise ValueError(f'direct representative screenshot unavailable: frame_{ms}')
            times.add(ms)
            if page_setting:
                regions[str(ms)] = page_setting
            frame = deepcopy(frames.get(ms, {'frameTimeMs': ms, 'ocrBlocks': []}))
            if page_setting:
                frame = filter_frame(frame, page_setting, ms, image.shape[1], image.shape[0])
            ocr.append({'frameTimeMs': ms, 'texts': [b.get('text', '') for b in frame.get('ocrBlocks', [])]})
        context.append({k: deepcopy(page[k]) for k in ('pageIndex', 'firstFrameTimeMs', 'lastFrameTimeMs',
                        'memberFrameTimesMs', 'representativeFrameTimesMs') if k in page} | {'ocrFrames': ocr})
    source = [dict(sourceType='transcript', sourceId=s['id'], startMs=s['startMs'], endMs=s['endMs'], quote=s['text']) for s in speech]
    images = [(ms, root / f'{ms}.jpg', 'original') for ms in sorted(times)]
    image_evidence = [dict(sourceType='image', sourceId=f'frame_{ms}', startMs=ms, endMs=ms, quote='课件截图') for ms in sorted(times)]
    payload = dict(_diagnosticTaskId=root.name,promptVersion=PROMPT_VERSION, instructions=INSTRUCTIONS, concepts=[], examples=[], connections=[],
        sourceEvidence=source, imageEvidence=image_evidence, firstHandSourceIds=[s['id'] for s in speech],
        firstHandImageIds=[f'frame_{ms}' for ms in sorted(times)], uncertainties=[], pageContext=context,
        effectiveTranscript=speech, _visualRegionsByFrame=regions, _directEvidence=True)
    payload['outlineHints'] = course.outline_hints([frames[ms] for ms in sorted(times)], root, regions)
    hashes = {f'frame_{ms}': hashlib.sha256(path.read_bytes()).hexdigest() for ms, path, _ in images}
    return payload, images, hashes


def build_direct_course_map(segments, pages, visuals, keyframe_dir, *, ask_json=None, checkpoint=None, signal=None, ignore_region=None):
    def check():
        if signal is not None and course._cancelled(signal):
            raise CancelledError('analysis_cancelled')
    def result(title, children, examples, errors, failed):
        value = course._result(title, children, examples, errors, failed)
        value['promptVersion'] = PROMPT_VERSION
        value['mindMapMode'] = 'direct'
        return value
    check()
    try:
        payload, images, hashes = _prepare(segments, pages, visuals, Path(keyframe_dir), ignore_region)
    except (ValueError, OSError) as error:
        return result('课程知识导图', [], [], [str(error)], True)
    if not images and not payload['sourceEvidence']:
        return result('课程知识导图', [], [], [], False)
    def generate():
        check()
        stage='provider'
        try:
            raw = (ask_json(deepcopy(payload), list(images)) if ask_json is not None else course._deepseek_course_json(deepcopy(payload), list(images),signal=signal))
            check()
            stage='validation'
            if isinstance(raw, str):
                from course_json import parse_course_json
                raw = parse_course_json(raw,task=Path(keyframe_dir).name)
            if (not isinstance(raw, dict) or not isinstance(raw.get('topic'), str) or not raw['topic'].strip()
                or not isinstance(raw.get('children'), list) or not isinstance(raw.get('examples'), list)
                or not isinstance(raw.get('uncertainties', []), list)):
                raise ValueError('malformed direct whole-course reply')
            value=course.finalize_course_reply(raw,payload,PROMPT_VERSION,diagnostic_root=Path(keyframe_dir))
            value['mindMapMode']='direct'
            if ask_json is None and value['status']=='completed':
                try:
                    from map_conversation import save_map_conversation
                    save_map_conversation(Path(keyframe_dir),payload,images,raw,value,course.INSTRUCTIONS,expected_hashes=hashes)
                except (OSError,ValueError):
                    import logging
                    logging.getLogger(__name__).warning('Map context snapshot unavailable; map itself remains usable')
            return value
        except CancelledError:
            raise
        except Exception as error:
            course.record_event('stage_failed',Path(keyframe_dir).name,operation='direct_map',stage=stage,error_type=type(error).__name__)
            # A limit/provider failure is explicit. Never retry using an image subset.
            return result('课程知识导图', [], [], [f'整课直接导图失败（整课材料完整提交，未分批或裁减）：{type(error).__name__}: {error}'], True)
    inputs = dict(promptVersion=PROMPT_VERSION, payload=payload, imageSha256=hashes,
                  model=os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash'),
                  endpoint=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'))
    value = checkpoint.run('directCourseMindMap', inputs, generate, lambda r: r.get('status') in ('completed', 'empty') and not course._cancelled(signal)) if checkpoint else generate()
    check()
    return value


def build_saved_direct_map(segments, pages, visuals, *, keyframe_dir, ignore_region=None):
    from group_scheduler import RunSignal
    root = Path(keyframe_dir)
    signal = RunSignal(root / '.analysis')
    # Explicit user regeneration always synthesizes anew; original media is reused.
    return build_direct_course_map(segments, pages, visuals, root, checkpoint=None,
                                   signal=signal, ignore_region=ignore_region)
