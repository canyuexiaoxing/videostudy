"""Day-one contract service. No media or AI analysis is performed here."""

from fastapi import FastAPI
from pydantic import BaseModel, field_validator
from ignored_region import normalize_setting as normalize_region
from fastapi import HTTPException
from typing import Literal

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


@app.post('/practice')
def practice(request: PracticeRequest):
    from practice import generate_practice
    from urllib.error import HTTPError
    try:
        return generate_practice(request.nodes, request.pages, request.count, request.difficulty)
    except HTTPError as error:
        raise HTTPException(424 if error.code == 402 else 502,
                            'practice_provider_payment_required' if error.code == 402 else 'practice_provider_failed') from error
    except (ValueError, RuntimeError) as error:
        raise HTTPException(422, str(error)) from error


class AnalyzeRequest(BaseModel):
    courseId: str


class TranscribeRequest(BaseModel):
    fileId: str
    visualAnalysisMode: str = "both"
    coarseChangePercent: float = 2.0
    coarseSampleSeconds: Literal[2, 3, 4] = 2
    subtitleCallbackToken: str | None = None
    ignoredRegion: dict | None = None

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
                                request.subtitleCallbackToken, coarse_sample_seconds=request.coarseSampleSeconds, **({"ignore_region": request.ignoredRegion} if request.ignoredRegion else {}))
        return analyze_file(request.fileId, request.visualAnalysisMode, request.coarseChangePercent,
                            coarse_sample_seconds=request.coarseSampleSeconds, **({"ignore_region": request.ignoredRegion} if request.ignoredRegion else {}))
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/mind-map")
def generate_mind_map(request: MindMapRequest) -> dict:
    return build_mind_map(request.segments, request.pageGroups)


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
        return build_overview(request.segments,request.pageGroups)
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
