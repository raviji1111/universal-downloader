import os
import uuid
import time
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def cleanup_old_files():
    """15 minute se purani temporary files delete karta hai taaki server full na ho."""
    now = time.time()
    for f in os.listdir(DOWNLOAD_DIR):
        path = os.path.join(DOWNLOAD_DIR, f)
        if os.path.isfile(path) and now - os.path.getmtime(path) > 900:
            try:
                os.remove(path)
            except Exception:
                pass

def get_base_ydl_opts():
    """Universal anti-block aur bina cookies ke YouTube/Insta/All-sites bypass settings."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        # 8x Fast Parallel Downloading (Badi videos aur HLS streams ke liye)
        'concurrent_fragment_downloads': 8,
        'retries': 10,
        'fragment_retries': 10,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        },
        # YouTube No-Cookie Bypass: Mobile aur Creator Studio clients use karta hai
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web_creator', 'mweb'],
                'player_skip': ['webpage', 'configs'],
            }
        }
    }
    # Agar future mein kabhi cookies.txt file rakho, toh automatically detect kar lega
    if os.path.exists('cookies.txt'):
        opts['cookiefile'] = 'cookies.txt'
    elif os.path.exists('/etc/secrets/cookies.txt'):
        opts['cookiefile'] = '/etc/secrets/cookies.txt'
    return opts

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'Kripya ek valid link paste karein.'}), 400

    ydl_opts = get_base_ydl_opts()
    ydl_opts['extract_flat'] = False

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            heights = set()
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('height'):
                    heights.add(f.get('height'))
            
            sorted_heights = sorted(list(heights), reverse=True)
            if not sorted_heights:
                sorted_heights = [1080, 720, 480, 360]
            
            return jsonify({
                'title': info.get('title', 'Media File'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration_string', 'Live / Unknown'),
                'extractor': info.get('extractor_key', 'Universal'),
                'resolutions': sorted_heights
            })
    except Exception as e:
        return jsonify({'error': f'Link analyze nahi ho paya. Check karein ki video public hai. ({str(e)[:120]})'}), 400

@app.route('/api/download', methods=['POST'])
def download_media():
    cleanup_old_files()
    data = request.get_json()
    url = data.get('url', '').strip()
    mode = data.get('mode', 'video')        # 'video' or 'audio'
    quality = data.get('quality', 'best')   # '2160', '1080', '720', '480', '360', 'best'
    ext = data.get('format', 'mp4')         # 'mp4', 'mkv', 'webm', 'mp3', 'm4a', 'wav', 'flac'

    if not url:
        return jsonify({'error': 'URL zaroori hai'}), 400

    file_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    ydl_opts = get_base_ydl_opts()
    ydl_opts['outtmpl'] = output_template
    ydl_opts['restrictfilenames'] = True

    if mode == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': ext,
            'preferredquality': '192',
        }]
    else:
        # Pehle single combined file dhundega (zero merge time), warna video+audio ko instant copy-merge karega
        if quality == 'best' or not str(quality).isdigit():
            ydl_opts['format'] = f'best[ext={ext}]/bestvideo+bestaudio/best'
        else:
            q = int(quality)
            ydl_opts['format'] = (
                f'best[height<={q}][ext={ext}]/'
                f'bestvideo[height<={q}]+bestaudio/'
                f'best[height<={q}]/best'
            )
        
        ydl_opts['merge_output_format'] = ext
        # FFmpeg ko bolta hai ki video re-encode na kare, seedha stream copy kare (2-second merge)
        ydl_opts['postprocessor_args'] = {
            'merger': ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k'] if ext == 'mp4' else ['-c', 'copy']
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')
            safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()[:80] or "download"

        # Download hui file ko locate karein (temp/part files ko chhod kar)
        downloaded_file = None
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(file_id) and not f.endswith(('.part', '.ytdl', '.temp')):
                downloaded_file = os.path.join(DOWNLOAD_DIR, f)
                break

        if not downloaded_file or not os.path.exists(downloaded_file) or os.path.getsize(downloaded_file) < 1024:
            return jsonify({'error': 'File generate nahi ho payi (0 bytes). Doosri quality ya format select karke try karein.'}), 500

        actual_ext = downloaded_file.split('.')[-1]
        download_name = f"{safe_title}.{actual_ext}"

        return send_file(
            downloaded_file,
            as_attachment=True,
            download_name=download_name
        )
    except Exception as e:
        return jsonify({'error': f'Download fail ho gaya: {str(e)[:150]}'}), 500

if __name__ == '__main__':
    # Railway, Koyeb, aur Render teeno ke PORT ko automatically support karta hai
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
