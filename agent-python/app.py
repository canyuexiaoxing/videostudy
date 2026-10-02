"""Day-one contract service. No media or AI analysis is performed here."""

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi import HTTPException

from transcription import transcribe_file
from analysis import analyze_file
from mind_map import build_mind_map

app = FastAPI(title="VideoStudy Agent Demo")


class AnalyzeRequest(BaseModel):
    courseId: str


class TranscribeRequest(BaseModel):
    fileId: str
    visualAnalysisMode: str = "both"
    coarseChangePercent: float = 2.0


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
        return analyze_file(request.fileId, request.visualAnalysisMode, request.coarseChangePercent)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/mind-map")
def generate_mind_map(request: MindMapRequest) -> dict:
    return build_mind_map(request.segments, request.pageGroups)
