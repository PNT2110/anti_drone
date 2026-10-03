# Hugging Face Space (Docker SDK, CPU). Built from the bundle that
# scripts/build_hf_space.py assembles; not meant to be built from the repo root.
FROM python:3.12-slim

# OpenCV (pulled in by ultralytics) needs these shared libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Spaces run the container as uid 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    ANTI_DRONE_DEVICE=cpu \
    ANTI_DRONE_VIDEO_IMGSZ=640 \
    ANTI_DRONE_MAX_VIDEO_TASKS=1

# backend/config.py locates the project by a directory named "web".
WORKDIR /home/user/app/web

COPY --chown=user requirements.txt .
# CPU-only torch first, so ultralytics does not pull the multi-GB CUDA build.
RUN pip install --no-cache-dir --user torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user web/ .

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
