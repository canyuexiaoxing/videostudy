from app import AnalyzeRequest, analyze_demo, health
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
