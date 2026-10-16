FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Optional isolated Torch environment; the existing Paddle dependencies stay unchanged.
ARG INSTALL_YOLO=0
COPY requirements-person.txt .
RUN if [ "$INSTALL_YOLO" = "1" ]; then python -m venv --system-site-packages /opt/person && /opt/person/bin/pip install --no-cache-dir torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu && /opt/person/bin/pip install --no-cache-dir -r requirements-person.txt; fi
COPY person_selection.py person_mask_worker.py app.py transcription.py analysis.py analysis_progress.py visual_evidence.py frame_stream.py ignored_region.py agent_review.py image_understanding.py slide_grouping.py page_understanding.py mind_map.py evidence_payload.py checkpoints.py subtitle_calibration.py subtitle_delivery.py chapters.py overview.py compatible_playback.py practice.py question_chat.py auto_region.py example_timeline.py knowledge_outline.py group_scheduler.py group_understanding.py grouped_analysis.py course_mind_map.py course_citations.py course_json.py course_outline.py model_diagnostics.py direct_analysis.py direct_course_map.py map_conversation.py practice_materials.py practice_history.py ./
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
