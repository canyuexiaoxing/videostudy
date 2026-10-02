from app import AnalyzeRequest, analyze_demo, health
from unittest.mock import patch
from transcription import transcribe_file


def test_demo_result_has_clickable_time_and_clear_label():
    assert health() == {"status": "ok"}
    result = analyze_demo(AnalyzeRequest(courseId="course-1"))
    assert result["points"][1]["startMs"] == 30000
    assert "尚未分析" in result["summary"]


def test_transcription_rejects_non_uuid_file_id():
    try:
        transcribe_file("../../secret")
    except ValueError:
        return
    raise AssertionError("expected invalid file ID to be rejected")


def test_saved_transcript_can_generate_mind_map_without_video():
    from app import MindMapRequest, generate_mind_map
    segments = [{"id": "t_1", "startMs": 1000, "endMs": 2000, "text": "课程原句"}]
    with patch("app.build_mind_map", return_value={"status": "completed"}) as build:
        result = generate_mind_map(MindMapRequest(segments=segments, pageGroups=[]))
    build.assert_called_once_with(segments, [])
    assert result["status"] == "completed"
