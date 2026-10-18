"""Opt-in streaming group analysis; legacy analyze_file stays unchanged by default."""
from person_visibility import grouping_context
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import logging
import os
from pathlib import Path
import threading
from time import perf_counter


def analyze_grouped_file(file_id, media_path, keyframe_dir, *, coarse_change_percent=3.0,
                         coarse_sample_seconds=2, subtitle_callback_token=None, ignore_region=None, person_selection_mode=None):
    # These imports are lazy: the default pipeline never instantiates the coordinator.
    import analysis as legacy
    person_context = legacy.person_selection_context(person_selection_mode) if person_selection_mode is not None else legacy.person_selection_context()
    person_options = {"person_selection_mode":person_selection_mode} if person_selection_mode is not None else {}
    from group_scheduler import ReadyGroupScheduler, RunSignal
    from group_understanding import analyze_group
    from course_mind_map import build_course_mind_map
    from slide_grouping import IncrementalPageGrouper

    root = Path(keyframe_dir)
    signal = RunSignal(root / '.analysis')
    signal.check()
    progress = legacy.AnalysisProgress(root / '.analysis')
    progress.enter('media', 0, 2)
    started = perf_counter()
    timings = {}
    metadata = media_path.stat()
    # Preserve media checkpoint identity, including legacy prompt versions, so old
    # successful media/coverage work can be replayed without streaming callbacks.
    checkpoint = legacy.Checkpoints(root / '.analysis', {
        'size': metadata.st_size, 'mtime': metadata.st_mtime_ns,
        'mode': 'both', 'threshold': coarse_change_percent, 'sampleSeconds': coarse_sample_seconds,
        **({'ignoredRegion': ignore_region} if ignore_region else {}),
        'ocr': legacy.OCR_MODEL_ID, 'ocrDevice': os.environ.get('OCR_DEVICE', 'cpu'),
        'speech': legacy.speech_checkpoint_key(),
        'model': os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash'),
        'endpoint': os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
        'prompts': [legacy.MAP_VERSION, legacy.PAGE_PROMPT_VERSION, legacy.REVIEW_VERSION, legacy.GROUPING_VERSION],
    })
    lock = threading.RLock()
    speech, frames, closed_groups = [], [], []
    segment_ids, frame_times = set(), set()
    speech_complete = False
    grouping_complete = False
    grouper = IncrementalPageGrouper(root, **({'ignore_region': ignore_region} if ignore_region else {}), **person_options)
    coordinator = ReadyGroupScheduler(root, analyze_group, max_workers=min(5, max(1, int(os.environ.get('PAGE_CONCURRENCY', '5')))),
                                     initial_groups=4, checkpoint=checkpoint, progress=progress, signal=signal,
                                     max_supplements=2)

    def snapshot():
        # The lock serializes callback state, while the coordinator owns inference.
        signal.check()
        groups = [dict(p, **({'_visualRegions': ignore_region} if ignore_region else {})) for p in closed_groups]
        coordinator.update(deepcopy(groups), deepcopy(speech), deepcopy(frames),
                           speech_complete=speech_complete, grouping_complete=grouping_complete)

    def on_segment(segment):
        signal.check()
        with lock:
            identity = segment.get('id')
            if identity in segment_ids:
                return
            segment_ids.add(identity)
            speech.append(deepcopy(segment))
            snapshot()

    def on_frame(evidence):
        signal.check()
        with lock:
            ms = evidence['frameTimeMs']
            if ms in frame_times:
                return
            frame_times.add(ms)
            frames.append(deepcopy(evidence))
            closed_groups.extend(grouper.add(deepcopy(evidence)))
            snapshot()

    def cached(stage, inputs, function, accept=lambda value: True):
        if stage != 'transcription':
            from frame_stream import FRAME_PIPELINE_VERSION
            inputs={'framePipeline':FRAME_PIPELINE_VERSION,'value':inputs}
        signal.check()
        value = checkpoint.run(stage, inputs, function, accept)
        signal.check()
        return value

    def timed(name, function):
        before = perf_counter()
        value = function()
        timings[name] = round((perf_counter() - before) * 1000)
        return value

    def transcribe():
        nonlocal speech_complete
        transcript = timed('transcription', lambda: cached('transcription', {},
                            lambda: legacy.transcribe_file(file_id, on_segment=on_segment)))
        # On checkpoint hit no callbacks ran. On a live run this is deduplicated.
        for item in transcript['segments']:
            on_segment(item)
        with lock:
            speech_complete = True
            snapshot()
        progress.unit_done('transcription', 'media')
        return transcript

    def recognize(worker):
        nonlocal grouping_complete
        evidence = timed('visualOcr', lambda: cached('visualOcr', person_context, lambda: worker.analyze(on_frame=on_frame)))
        for item in sorted(evidence, key=lambda f: f['frameTimeMs']):
            on_frame(item)
        with lock:
            closed_groups.extend(grouper.finish())
            grouping_complete = True
            snapshot()
        progress.unit_done('visualOcr', 'media')
        return evidence

    def checked_capture(function):
        def capture(*args, **kwargs):
            signal.check()
            value = function(*args, **kwargs)
            signal.check()
            return value
        return capture

    try:
        with legacy.VisualOcrWorker(media_path, root, page_change_fraction=coarse_change_percent / 100,
                                   sample_seconds=coarse_sample_seconds,
                                   **({'ignore_region': ignore_region} if ignore_region else {}), **person_options) as worker:
            # Grouped mode always retains concurrent media extraction.
            with ThreadPoolExecutor(max_workers=2) as pool:
                speech_job = pool.submit(transcribe)
                visual_job = pool.submit(recognize, worker)
                transcript, visuals = speech_job.result(), visual_job.result()
            timings['groupAnalysis'] = round((perf_counter() - started) * 1000)
            signal.check()
            progress.enter('coverage', 1)
            visuals, review = timed('coverageReview', lambda: cached('coverageReview',
                {'speech': transcript, 'visuals': visuals},
                lambda: legacy.review_visual_coverage(duration_ms=legacy.media_duration_ms(media_path),
                    segments=transcript['segments'], visuals=visuals,
                    capture=checked_capture(worker.capture), capture_batch=checked_capture(worker.capture_batch)),
                lambda value: value[1].get('status') in ('completed', 'not_applicable')))
        signal.check()
        progress.enter('grouping', 2)
        before = perf_counter()
        final_pages, transitions = timed('pageGrouping', lambda: cached('pageGrouping',
            {'visuals': visuals, 'speech': transcript['segments'], **grouping_context(root,visuals,person_selection_mode)},
            lambda: legacy.group_pages(visuals, root, transcript['segments'],
                **({'ignore_region': ignore_region} if ignore_region else {}), **person_options)))
        if ignore_region:
            final_pages = [dict(p, _visualRegions=ignore_region) for p in final_pages]
        progress.enter('pages', 3, len(final_pages))
        pages = coordinator.finish(final_pages, transcript['segments'], visuals)
        signal.check()
        timings['refinement'] = round((perf_counter() - before) * 1000)
        pages_failed = any((p.get('groupUnderstanding') or {}).get('status') == 'failed' for p in pages)
        if not pages_failed:
            progress.enter('materials', 4, 1)

        def course_map():
            signal.check()
            value = timed('courseMap', lambda: build_course_mind_map(transcript['segments'], pages, visuals, root,
                                 checkpoint=checkpoint, signal=signal) if pages else
                          legacy.build_mind_map(transcript['segments'], [], checkpoint=checkpoint))
            signal.check()
            if value.get('status') != 'failed':
                progress.unit_done('mindMap', 'materials')
            return value

        mind_map = course_map()
        overview_result = None
        signal.check()
        clean_pages = [{k: deepcopy(v) for k, v in p.items() if not k.startswith('_')} for p in pages]
        if subtitle_callback_token:
            try:
                legacy.publish_subtitle_source(file_id, subtitle_callback_token, transcript['language'],
                                               transcript['segments'], clean_pages)
            except Exception as error:
                logging.getLogger(__name__).warning('Unable to schedule subtitle source: %s', type(error).__name__)
        signal.check()
        if not pages_failed and mind_map.get('status') != 'failed':
            progress.enter('saving', 4)
        timings['total'] = round((perf_counter() - started) * 1000)
        return {'language': transcript['language'], 'segments': transcript['segments'], 'visualEvidence': visuals,
                'pageGroups': clean_pages, 'mindMap': mind_map, 'overview': overview_result,
                'transitionFrameTimesMs': transitions, 'visualAnalysisMode': 'both',
                'coarseChangePercent': coarse_change_percent, 'coarseSampleSeconds': coarse_sample_seconds,
                'groupingVersion': legacy.GROUPING_VERSION, 'ocrModelId': legacy.OCR_MODEL_ID if visuals else None,
                'imageModelId': os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash') if pages else None,
                'review': review, 'stageTimingsMs': timings, 'reusedCheckpoints': checkpoint.hits,
                'groupedAnalysis': True}
    except BaseException:
        coordinator.cancel()
        raise
    finally:
        coordinator.close()


def build_saved_group_map(segments, pages, visuals, *, keyframe_dir=None, ignore_region=None):
    """Explicit refresh only: reuse group candidates, analyze only missing groups."""
    import analysis as legacy
    from course_mind_map import build_course_mind_map
    from group_understanding import analyze_group, GROUP_PROMPT_VERSION
    from group_scheduler import RunSignal
    if not pages:
        return legacy.build_mind_map(segments, [])
    needs_refresh = any(not isinstance(p.get('groupUnderstanding'), dict) for p in pages)
    needs_raw = needs_refresh or any((p.get('groupUnderstanding') or {}).get('forwardImageTimesMs') for p in pages)
    if needs_raw and keyframe_dir is None:
        raise ValueError('courseId is required to refresh historical screenshot evidence')
    root = Path(keyframe_dir) if keyframe_dir is not None else Path('__unavailable_saved_media__')
    signal = RunSignal(root / '.analysis') if keyframe_dir is not None else None
    if signal:
        signal.check()
    ready_pages = deepcopy(pages)
    if ignore_region:
        ready_pages = [dict(p, _visualRegions=ignore_region) for p in ready_pages]
    by_time = {f['frameTimeMs']: deepcopy(f) for f in visuals if isinstance(f, dict) and
               type(f.get('frameTimeMs')) is int}
    if needs_refresh:
        # Old records may not contain visualEvidence, but frame timestamps plus
        # existing JPEGs and their saved OCR constitute real historical evidence.
        for p in ready_pages:
            for ms in p.get('memberFrameTimesMs', []):
                if type(ms) is not int or not (root / f'{ms}.jpg').is_file():
                    continue
                by_time.setdefault(ms, {'frameTimeMs': ms, 'ocrBlocks': [
                    {'text': line['text']} for line in p.get('ocrLines', [])
                    if isinstance(line, dict) and line.get('sourceFrameTimeMs') == ms and
                    isinstance(line.get('text'), str)]})
        missing = [p for p in ready_pages if not isinstance(p.get('groupUnderstanding'), dict)]
        for p in missing:
            if not any(type(ms) is int and ms in by_time and (root / f'{ms}.jpg').is_file()
                       for ms in p.get('representativeFrameTimesMs', [])):
                raise ValueError('historical representative screenshot is unavailable')
        checkpoint = legacy.Checkpoints(root / '.analysis', {'groupedRefresh': GROUP_PROMPT_VERSION,
                    'model': os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash'),
                    'endpoint': os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')})
        def refresh(p):
            signal.check()
            value = checkpoint.run(f'groupRefresh:{p["pageIndex"]}',
                {'page': p, 'pages': ready_pages, 'segments': segments, 'visuals': list(by_time.values())},
                lambda: analyze_group(p, ready_pages, by_time, root, segments, 'both', signal=signal),
                lambda value: (value.get('groupUnderstanding') or {}).get('status') in ('completed', 'partial'))
            signal.check()
            if ignore_region:
                value = dict(value, _visualRegions=ignore_region)
            return value
        with ThreadPoolExecutor(max_workers=min(5, max(1, int(os.environ.get('PAGE_CONCURRENCY', '5'))))) as pool:
            refreshed = {p['pageIndex']: value for p, value in zip(missing, pool.map(refresh, missing))}
        ready_pages = [refreshed.get(p['pageIndex'], p) for p in ready_pages]
    else:
        checkpoint = None
    if signal:
        signal.check()
    # Reuse any group work above, but never replay the final map on explicit regeneration.
    value = build_course_mind_map(segments, ready_pages, list(by_time.values()), root,
                                 checkpoint=None, signal=signal)
    if signal:
        signal.check()
    return value
