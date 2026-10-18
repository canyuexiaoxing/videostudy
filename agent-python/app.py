"""Day-one contract service. No media or AI analysis is performed here."""

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator
from ignored_region import normalize_setting as normalize_region
from fastapi import HTTPException
from typing import Literal
from json import JSONDecodeError
from concurrent.futures import CancelledError

from transcription import transcribe_file
from analysis import analyze_file
from mind_map import build_mind_map

app = FastAPI(title="VideoStudy Agent Demo")
from compatible_playback import router as compatibility_router
app.include_router(compatibility_router)


class QuestionChatRequest(BaseModel):
    context: dict
    history: list[dict] = []
    message: str


@app.post('/question-chat')
def question_chat(request: QuestionChatRequest):
    from question_chat import reply_to_question
    from urllib.error import HTTPError, URLError
    try:
        return reply_to_question(request.context, request.history, request.message)
    except HTTPError as error:
        raise HTTPException(502, 'chat_provider_failed') from error
    except (URLError, TimeoutError, RuntimeError) as error:
        raise HTTPException(503, 'chat_provider_unavailable') from error
    except ValueError as error:
        raise HTTPException(422, 'invalid_chat_reply') from error


class PracticeRequest(BaseModel):
    nodes: list[dict]
    pages: list[dict] = []
    count: int = 5
    difficulty: str = 'basic'
    mode: Literal['legacy','map_context','related_materials'] = 'legacy'
    courseId: str | None = None
    practiceHistory: list[dict] = Field(default_factory=list,max_length=50)
    scopeNodeId: str | None = None
    mindMap: dict | None = None
    sourceSegments: list[dict] = []
    pageGroups: list[dict] = []
    visualEvidence: list[dict] = []
    ignoredRegion: dict | None = None


@app.post('/practice')
def practice(request: PracticeRequest):
    from practice import generate_practice
    from urllib.error import HTTPError
    try:
        if request.mode=='legacy':return generate_practice(request.nodes, request.pages, request.count, request.difficulty,history=request.practiceHistory)
        if not request.courseId or not request.mindMap:raise ValueError('practice_evidence_missing')
        root=_analysis_directory(request.courseId).parent
        if request.mode=='map_context':
            from map_conversation import load_map_conversation
            context=load_map_conversation(root,request.mindMap)
        else:
            from practice_materials import related_materials
            context=related_materials(request.nodes,request.pageGroups,request.mindMap,request.sourceSegments,
                request.visualEvidence,root,request.scopeNodeId,request.ignoredRegion)
        context['_diagnosticTaskId']=request.courseId
        return generate_practice(request.nodes,request.pages,request.count,request.difficulty,mode=request.mode,context=context,
            whole_course=request.scopeNodeId==request.mindMap.get('root',{}).get('id'),history=request.practiceHistory)
    except HTTPError as error:
        if error.code==413:raise HTTPException(422,'practice_context_too_large') from error
        if error.code in (400,422):raise HTTPException(422,'practice_provider_rejected') from error
        raise HTTPException(424 if error.code == 402 else 502,
                            'practice_provider_payment_required' if error.code == 402 else 'practice_provider_failed') from error
    except JSONDecodeError as error:
        raise HTTPException(422,'practice_provider_invalid_json') from error
    except (ValueError, RuntimeError) as error:
        raise HTTPException(422, str(error)) from error


class AnalyzeRequest(BaseModel):
    courseId: str


class TranscribeRequest(BaseModel):
    fileId: str
    visualAnalysisMode: str = "both"
    coarseChangePercent: float = 3.0
    coarseSampleSeconds: Literal[2, 3, 4] = 2
    subtitleCallbackToken: str | None = None
    personSelectionMode: Literal['off', 'adjacent'] | None = None
    ignoredRegion: dict | None = None
    groupedAnalysis: bool = False
    mindMapMode: Literal['legacy', 'grouped', 'direct'] | None = None

    @field_validator('ignoredRegion', mode='before')
    @classmethod
    def validate_region(cls, value):
        return normalize_region(value)


class SubtitleRequest(BaseModel):
    language: str
    segments: list[dict]
    pageGroups: list[dict] = []
    targetLanguage: Literal['source', 'zh', 'en'] = 'source'


class MindMapRequest(BaseModel):
    segments: list[dict]
    pageGroups: list[dict] = []
    courseId: str | None = None
    groupedAnalysis: bool = False
    mindMapMode: Literal['legacy', 'grouped', 'direct'] | None = None
    visualAnalysisMode: str = 'both'
    visualEvidence: list[dict] = []
    ignoredRegion: dict | None = None
    mindMap: dict | None = None

    @field_validator('ignoredRegion', mode='before')
    @classmethod
    def validate_region(cls, value):
        return normalize_region(value)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze-demo")
def analyze_demo(request: AnalyzeRequest) -> dict:
    return {
        "summary": "接口联调示例：尚未分析视频内容",
        "points": [
            {"id": "demo-1", "title": "示例节点：课程开头", "startMs": 0, "endMs": 10000,
             "evidence": "演示数据，不是视频转写或 AI 判断"},
            {"id": "demo-2", "title": "示例节点：30 秒处", "startMs": 30000, "endMs": 40000,
             "evidence": "演示数据，不是视频转写或 AI 判断"},
        ],
    }


@app.post("/transcribe")
def transcribe(request: TranscribeRequest) -> dict:
    try:
        return transcribe_file(request.fileId)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/analyze")
def analyze(request: TranscribeRequest) -> dict:
    try:
        if request.subtitleCallbackToken:
            return analyze_file(request.fileId, request.visualAnalysisMode, request.coarseChangePercent,
                                request.subtitleCallbackToken, coarse_sample_seconds=request.coarseSampleSeconds, **({"ignore_region": request.ignoredRegion} if request.ignoredRegion else {}),
                                **({"grouped_analysis": True} if request.groupedAnalysis else {}),
                                **({"mind_map_mode": request.mindMapMode} if request.mindMapMode is not None else {}),
                                **({"person_selection_mode": request.personSelectionMode} if request.personSelectionMode is not None else {}))
        return analyze_file(request.fileId, request.visualAnalysisMode, request.coarseChangePercent,
                            coarse_sample_seconds=request.coarseSampleSeconds, **({"ignore_region": request.ignoredRegion} if request.ignoredRegion else {}),
                                **({"grouped_analysis": True} if request.groupedAnalysis else {}),
                                **({"mind_map_mode": request.mindMapMode} if request.mindMapMode is not None else {}),
                                **({"person_selection_mode": request.personSelectionMode} if request.personSelectionMode is not None else {}))
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except CancelledError as error:
        raise HTTPException(status_code=409, detail='analysis_cancelled') from error


@app.post("/mind-map")
def generate_mind_map(request: MindMapRequest) -> dict:
    mode = request.mindMapMode or ('grouped' if request.groupedAnalysis else 'legacy')
    if mode == 'legacy':
        return build_mind_map(request.segments, request.pageGroups)
    try:
        if request.visualAnalysisMode != 'both':
            raise ValueError('groupedAnalysis requires visualAnalysisMode both')
        if mode == 'direct':
            if not request.courseId:raise ValueError('courseId is required for direct representative images')
            from direct_course_map import build_saved_direct_map
            return build_saved_direct_map(request.segments,request.pageGroups,request.visualEvidence,
                keyframe_dir=_analysis_directory(request.courseId).parent,ignore_region=request.ignoredRegion)
        from grouped_analysis import build_saved_group_map
        directory = _analysis_directory(request.courseId).parent if request.courseId else None
        return build_saved_group_map(request.segments, request.pageGroups, request.visualEvidence,
                                     keyframe_dir=directory, ignore_region=request.ignoredRegion)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(400, str(error)) from error
    except CancelledError as error:
        raise HTTPException(409, 'analysis_cancelled') from error


@app.post('/subtitles')
def generate_subtitles(request: SubtitleRequest) -> dict:
    from subtitle_calibration import calibrate_subtitles
    try:
        return calibrate_subtitles(request.language, request.segments, request.pageGroups,
                                   request.targetLanguage)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post('/chapters')
def generate_chapters(request: MindMapRequest) -> dict:
    from chapters import build_chapters
    return build_chapters(request.segments, request.pageGroups)

@app.post('/overview')
def generate_overview(request: MindMapRequest) -> dict:
    from overview import build_overview
    from urllib.error import HTTPError
    try:
        return build_overview(request.segments,request.pageGroups,mind_map=request.mindMap,visuals=request.visualEvidence,course_id=request.courseId)
    except HTTPError as error:
        if error.code==402:
            raise HTTPException(status_code=424,detail='overview_provider_payment_required') from error
        raise


class RegionFramesRequest(BaseModel):
    frames: list[dict]

from threading import BoundedSemaphore
_region_slots = BoundedSemaphore(2)

@app.post('/video-region-detections')
def video_region_detections(request: RegionFramesRequest):
    from auto_region import detect_frames
    from urllib.error import HTTPError,URLError
    if not _region_slots.acquire(blocking=False):raise HTTPException(429,'region_detector_busy')
    try:return {'detections':detect_frames(request.frames)}
    except ValueError as error:raise HTTPException(422,str(error)) from error
    except HTTPError as error:raise HTTPException(502,'region_provider_failed') from error
    except (RuntimeError,URLError,TimeoutError,KeyError,TypeError) as error:raise HTTPException(503,'region_provider_unavailable') from error
    finally:_region_slots.release()


class AnalysisControlRequest(BaseModel):
    fileId: str


def _analysis_directory(file_id):
    import os
    from pathlib import Path
    from uuid import UUID
    try:
        identity = str(UUID(file_id))
    except (ValueError, TypeError, AttributeError) as error:
        raise HTTPException(400, 'invalid_file_id') from error
    root = Path(os.environ.get('KEYFRAME_DIR', '../.local/keyframes')).resolve()
    target = (root / identity / '.analysis').resolve()
    if not target.is_relative_to(root):
        raise HTTPException(400, 'invalid_file_id')
    return target


@app.post('/analysis-cancel')
def cancel_analysis(request: AnalysisControlRequest):
    from group_scheduler import cancel_run
    cancel_run(_analysis_directory(request.fileId))
    return {'status': 'cancelled'}


@app.post('/analysis-reset')
def reset_analysis(request: AnalysisControlRequest):
    from group_scheduler import reset_run
    reset_run(_analysis_directory(request.fileId))
    return {'status': 'ready'}
