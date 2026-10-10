FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py transcription.py analysis.py visual_evidence.py agent_review.py image_understanding.py slide_grouping.py page_understanding.py mind_map.py evidence_payload.py checkpoints.py subtitle_calibration.py subtitle_delivery.py chapters.py overview.py compatible_playback.py practice.py question_chat.py ./
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
