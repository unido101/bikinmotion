# Bangun dari AKAR repo:  docker build -f worker/Dockerfile -t bikinmotion-worker .
# Dengan Whisper (sinkron per kata, lebih akurat, image lebih besar):  --build-arg WHISPER=1
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY requirements.txt .
ARG WHISPER=0
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$WHISPER" = "1" ]; then pip install --no-cache-dir faster-whisper \
    && python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"; fi

COPY pipeline pipeline
COPY worker worker
COPY styles styles
COPY assets assets

ENV PYTHONUNBUFFERED=1 HF_HOME=/home/app/.cache/huggingface
USER app
CMD ["python", "-m", "worker.main"]
