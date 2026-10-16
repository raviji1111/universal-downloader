FROM python:3.11-slim

# FFmpeg (merging ke liye) aur Aria2 (high-speed downloading ke liye) install karein
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg aria2 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# Hamesha latest yt-dlp nightly/master install karein taaki YouTube block na kar paye
ENV CACHE_BUST=1
RUN pip install --no-cache-dir --upgrade -r requirements.txt && \
    pip install --no-cache-dir --upgrade --pre "yt-dlp[default]"

COPY . .

EXPOSE 10000

# Dynamic PORT support: Railway, Koyeb aur Render sab par automatic chalega
CMD sh -c "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --threads 4 --timeout 900 app:app"
