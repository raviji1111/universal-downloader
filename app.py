import os
import uuid
import threading
import time
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def cleanup_old_files():
    """Deletes temporary downloaded files older than 10 minutes to prevent server crashes."""
    now = time.time()
    for f in os.listdir(DOWNLOAD_DIR):
        path = os.path.join(DOWNLOAD_DIR, f)
        if os.path.isfile(path) and now - os.path.getmtime(path) > 600:
            try:
                os.remove(path)
            except Exception:
                pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'Please paste a valid share link.'}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Gather available video resolutions
            heights = set()
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('height'):
                    heights.add(f.get('height'))
            
            sorted_heights = sorted(list(heights), reverse=True)
            
            return jsonify({
                'title': info.get('title', 'Media File'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration_string', 'N/A'),
                'extractor': info.get('extractor_key', 'Web'),
                'resolutions': sorted_heights
            })
    except Exception as e:
        return jsonify({'error': f'Could not fetch media info. Make sure the link is public. ({str(e)})'}), 400

@app.route('/api/download', methods=['POST'])
def download_media():
    cleanup_old_files()
    data = request.get_json()
    url = data.get('url', '').strip()
    mode = data.get('mode', 'video')        # 'video' or 'audio'
    quality = data.get('quality', 'best')   # e.g., '1080', '720', 'best'
    ext = data.get('format', 'mp4')         # 'mp4', 'webm', 'mkv', 'mp3', 'm4a', 'wav'

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    ydl_opts = {
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': True,
    }

    if mode == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': ext,
            'preferredquality': '192',
        }]
    else:
        if quality == 'best' or not quality.isdigit():
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
        else:
            ydl_opts['format'] = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best'
        ydl_opts['merge_output_format'] = ext

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')
            safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip() or "download"

        # Locate the generated output file
        downloaded_file = None
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(file_id):
                downloaded_file = os.path.join(DOWNLOAD_DIR, f)
                break

        if not downloaded_file or not os.path.exists(downloaded_file):
            return jsonify({'error': 'Failed to process media file.'}), 500

        actual_ext = downloaded_file.split('.')[-1]
        download_name = f"{safe_title}.{actual_ext}"

        return send_file(
            downloaded_file,
            as_attachment=True,
            download_name=download_name
        )
    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
