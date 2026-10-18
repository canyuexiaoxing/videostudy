"""Local media preparation followed by one direct whole-course synthesis."""
from person_visibility import grouping_context
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
import os
import logging


def analyze_direct_file(file_id, media_path, keyframe_dir, *, coarse_change_percent=3.0,
                        coarse_sample_seconds=2, subtitle_callback_token=None, ignore_region=None, person_selection_mode=None):
    import analysis as legacy
    person_context = legacy.person_selection_context(person_selection_mode) if person_selection_mode is not None else legacy.person_selection_context()
    person_options = {"person_selection_mode":person_selection_mode} if person_selection_mode is not None else {}
    from group_scheduler import RunSignal
    from direct_course_map import build_direct_course_map, PROMPT_VERSION
    root = Path(keyframe_dir)
    signal = RunSignal(root / '.analysis')
    progress = legacy.AnalysisProgress(root / '.analysis')
    progress.enter('media', 0, 2)
    started, timings = perf_counter(), {}
    stat = media_path.stat()
    checkpoint = legacy.Checkpoints(root / '.analysis', {
        'size': stat.st_size, 'mtime': stat.st_mtime_ns, 'mode': 'both',
        'threshold': coarse_change_percent, 'sampleSeconds': coarse_sample_seconds,
        **({'ignoredRegion': ignore_region} if ignore_region else {}),
        'ocr': legacy.OCR_MODEL_ID, 'ocrDevice': os.environ.get('OCR_DEVICE', 'cpu'),
        'speech': legacy.speech_checkpoint_key(),
        'model': os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash'),
        'endpoint': os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
        'prompts': [legacy.MAP_VERSION, legacy.PAGE_PROMPT_VERSION, legacy.REVIEW_VERSION, legacy.GROUPING_VERSION]})
    def cached(stage, inputs, function, accept=None):
        if stage != 'transcription':
            from frame_stream import FRAME_PIPELINE_VERSION
            inputs={'framePipeline':FRAME_PIPELINE_VERSION,'value':inputs}
        signal.check()
        before = perf_counter()
        def checked():
            signal.check()
            value = function()
            signal.check()
            return value
        value = checkpoint.run(stage, inputs, checked, accept or (lambda value: True))
        signal.check()
        timings[stage] = round((perf_counter() - before) * 1000)
        return value
    def transcribe():
        value = cached('transcription', {}, lambda: legacy.transcribe_file(file_id))
        progress.unit_done('transcription', 'media')
        return value
    with legacy.VisualOcrWorker(media_path, root, page_change_fraction=coarse_change_percent / 100,
            sample_seconds=coarse_sample_seconds, **({'ignore_region': ignore_region} if ignore_region else {}), **person_options) as worker:
        def recognize():
            value = cached('visualOcr', person_context, worker.analyze)
            progress.unit_done('visualOcr', 'media')
            return value
        with ThreadPoolExecutor(max_workers=2) as pool:
            speech_job, visual_job = pool.submit(transcribe), pool.submit(recognize)
            transcript, visuals = speech_job.result(), visual_job.result()
        signal.check()
        progress.enter('coverage', 1)
        def checked_capture(function):
            def capture(*args, **kwargs):
                signal.check()
                value = function(*args, **kwargs)
                signal.check()
                return value
            return capture
        visuals, review = cached('coverageReview', {'speech': transcript, 'visuals': visuals},
            lambda: legacy.review_visual_coverage(duration_ms=legacy.media_duration_ms(media_path),
                segments=transcript['segments'], visuals=visuals,
                capture=checked_capture(worker.capture), capture_batch=checked_capture(worker.capture_batch)),
            lambda value: value[1].get('status') in ('completed', 'not_applicable'))
    signal.check()
    if review.get('status') not in ('completed', 'not_applicable'):
        raise RuntimeError('Coverage review incomplete; retry before direct synthesis')
    progress.enter('grouping', 2)
    pages, transitions = cached('directPageGrouping', {'visuals': visuals, 'speech': transcript['segments'],
        'version': legacy.GROUPING_VERSION, **grouping_context(root,visuals,person_selection_mode)}, lambda: legacy.group_pages(visuals, root, transcript['segments'],
        ask_json=lambda _: {'samePage': False, 'reason': 'local direct boundary; conservatively split'},
        **({'ignore_region': ignore_region} if ignore_region else {}), **person_options))
    progress.enter('materials', 4, 1)
    before = perf_counter()
    mind_map = build_direct_course_map(transcript['segments'], pages, visuals, root,
                    checkpoint=checkpoint, signal=signal, ignore_region=ignore_region)
    timings['mindMap'] = round((perf_counter() - before) * 1000)
    signal.check()
    if mind_map.get('status') != 'failed':
        progress.unit_done('mindMap', 'materials')
        progress.enter('saving', 4)
    if subtitle_callback_token:
        try:
            legacy.publish_subtitle_source(file_id, subtitle_callback_token, transcript['language'], transcript['segments'], pages)
        except Exception as error:
            logging.getLogger(__name__).warning('Unable to schedule subtitle source: %s', type(error).__name__)
    signal.check()
    timings['total'] = round((perf_counter() - started) * 1000)
    return dict(language=transcript['language'], segments=transcript['segments'], visualEvidence=visuals,
        pageGroups=pages, mindMap=mind_map, overview=None,
        transitionFrameTimesMs=transitions, visualAnalysisMode='both', coarseChangePercent=coarse_change_percent,
        coarseSampleSeconds=coarse_sample_seconds, groupingVersion=legacy.GROUPING_VERSION,
        ocrModelId=legacy.OCR_MODEL_ID if visuals else None, imageModelId=os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash'),
        review=review, stageTimingsMs=timings, reusedCheckpoints=checkpoint.hits, groupedAnalysis=False, mindMapMode='direct')
