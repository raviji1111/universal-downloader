FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg aria2 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Railway ko naya yt-dlp install karne par force karne ke liye isko 2 kar diya hai
ENV CACHE_BUST=2

# Ye direct GitHub master branch se sabse latest daily-fix version download karega
RUN pip install --no-cache-dir --upgrade -r requirements.txt && \
    pip install --no-cache-dir --force-reinstall https://github.com/yt-dlp/yt-dlp/archive/master.tar.gz

COPY . .

EXPOSE 10000

CMD sh -c "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --threads 4 --timeout 900 app:app"
