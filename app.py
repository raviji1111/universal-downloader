import os, uuid, time
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp

app = Flask(__name__)
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def cleanup_old_files():
    now = time.time()
    for f in os.listdir(DOWNLOAD_DIR):
        path = os.path.join(DOWNLOAD_DIR, f)
        if os.path.isfile(path) and now - os.path.getmtime(path) > 900:
            try: os.remove(path)
            except: pass

def get_base_ydl_opts():
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'concurrent_fragment_downloads': 8,
        'retries': 10,
        'age_limit': 21, # Bypasses age restrictions on adult/restricted sites
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        }
    }
    cookie_path = os.path.join(os.getcwd(), 'cookies.txt')
    if os.path.exists(cookie_path):
        opts['cookiefile'] = cookie_path
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

    def extract(target_url):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(target_url, download=False)

    try:
        info = extract(url)
    except Exception as e:
        # Auto-Fallback: Agar main extractor crash ho, toh generic raw scraper use karein
        try:
            info = extract(f"generic:{url}")
        except Exception as generic_e:
            return jsonify({'error': f'Analyze Error: Site ne temporarily API change kiya hai. (Error: {str(e)[:80]})'}), 400
            
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
        'extractor': info.get('extractor_key', 'Universal System'),
        'resolutions': sorted_heights
    })

@app.route('/api/download', methods=['POST'])
def download_media():
    cleanup_old_files()
    data = request.get_json()
    url = data.get('url', '').strip()
    mode = data.get('mode', 'video')        
    quality = data.get('quality', 'best')   
    ext = data.get('format', 'mp4')         

    if not url:
        return jsonify({'error': 'URL is required'}), 400

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
        if quality == 'best' or not str(quality).isdigit():
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
        else:
            q = int(quality)
            ydl_opts['format'] = f'bestvideo[height<={q}]+bestaudio/bestvideo+bestaudio/best'
        
        ydl_opts['merge_output_format'] = ext

    def download_file(target_url):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(target_url, download=True)

    try:
        try:
            info = download_file(url)
        except Exception:
            # Download phase Auto-Fallback
            info = download_file(f"generic:{url}")
            
        title = info.get('title', 'video')
        safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()[:60] or "download"

        downloaded_file = None
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(file_id) and not f.endswith(('.part', '.ytdl', '.temp')):
                downloaded_file = os.path.join(DOWNLOAD_DIR, f)
                break

        if not downloaded_file or not os.path.exists(downloaded_file):
            return jsonify({'error': 'Server par file generate nahi ho payi.'}), 500

        actual_ext = downloaded_file.split('.')[-1]
        download_name = f"{safe_title}.{actual_ext}"

        return send_file(
            downloaded_file,
            as_attachment=True,
            download_name=download_name
        )
    except Exception as e:
        return jsonify({'error': f'Download fail ho gaya. (Error: {str(e)[:100]})'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
