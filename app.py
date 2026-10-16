import os
import uuid
import time
from flask import Flask, render_template, request, jsonify
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
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')
            safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip() or "download"

            # Direct stream link extract karna taaki server par load na pade
            formats = info.get('formats', [])
            direct_url = None
            
            # Best progressive format dhundho jisme video aur audio dono hon
            for f in reversed(formats):
                if f.get('url') and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    direct_url = f.get('url')
                    break
            
            # Agar progressive na mile toh sabse aakhri available format utha lo
            if not direct_url and formats:
                direct_url = formats[-1].get('url')

            if not direct_url:
                return jsonify({'error': 'Could not extract direct download link.'}), 400

            return jsonify({
                'success': True,
                'redirect_url': direct_url,
                'title': safe_title
            })

    except Exception as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
