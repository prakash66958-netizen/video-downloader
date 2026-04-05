from flask import Flask, render_template, request, jsonify, send_from_directory, Response
import yt_dlp
import os
import time
import uuid
import re
import threading

app = Flask(__name__)

import platform

# Folder to store finished downloads
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Dynamic path to FFmpeg: use local Windows path if available, otherwise assume system path
if platform.system() == "Windows":
    FFMPEG_PATH = r'C:\Users\praka\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin'
else:
    FFMPEG_PATH = None # On Linux/Render, it will be in the system PATH automatically

# Dictionary to store progress: { download_id: progress_string }
progress_data = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_info', methods=['POST'])
def get_info():
    urls = request.json.get('urls')
    if not urls or not isinstance(urls, list):
        return jsonify({'error': 'No URLs provided'}), 400

    results = []
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for url in urls:
        if not url.strip(): continue
        search_query = url.strip()
        if not (url.startswith('http://') or url.startswith('https://')):
            search_query = f"ytsearch5:{url}"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
                entries = info.get('entries', [info])
                for entry in entries:
                    formats = []
                    seen_labels = set()
                    raw_formats = entry.get('formats', [])
                    raw_formats.sort(key=lambda x: (x.get('height') or 0, x.get('abr') or 0), reverse=True)
                    for f in raw_formats:
                        height = f.get('height') or 0
                        if height > 1080: continue
                        label = f"🎬 {height}p" if height > 0 else f"🎵 Audio ({int(f.get('abr', 0))}kbps)"
                        if label and label not in seen_labels:
                            formats.append({'format_id': f.get('format_id'), 'ext': f.get('ext'), 'resolution': label, 'filesize': f.get('filesize'), 'url': f.get('url')})
                            seen_labels.add(label)
                    results.append({'url_original': entry.get('webpage_url') or url, 'title': entry.get('title'), 'thumbnail': entry.get('thumbnail'), 'uploader': entry.get('uploader'), 'formats': formats})
        except Exception as e:
            results.append({'url_original': url, 'error': str(e)})
    return jsonify({'results': results})

@app.route('/progress/<download_id>')
def progress_stream(download_id):
    def generate():
        last_msg = ""
        while True:
            msg = progress_data.get(download_id, "Initializing...")
            if msg != last_msg:
                yield f"data: {msg}\n\n"
                last_msg = msg
            if "Finished" in msg or "Error" in msg:
                break
            time.sleep(0.3)
    return Response(generate(), mimetype='text/event-stream', headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'})

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    mode = data.get('mode')
    download_id = data.get('download_id')

    if not url or not download_id:
        return jsonify({'error': 'Missing parameters'}), 400

    def my_hook(d):
        if d['status'] == 'downloading':
            p_str = d.get('_percent_str', '0%')
            match = re.search(r'(\d+\.?\d*)%', p_str)
            if match:
                progress_data[download_id] = f"Downloading Video: {match.group(1)}%"
        elif d['status'] == 'finished':
            progress_data[download_id] = "Converting & Saving... almost ready!"

    output_template = os.path.join(DOWNLOAD_FOLDER, f'%(title)s_{int(time.time())}.%(ext)s')
    ydl_opts = {'outtmpl': output_template, 'quiet': True, 'ffmpeg_location': FFMPEG_PATH, 'progress_hooks': [my_hook], 'noprogress': False}

    if mode.startswith('mp3'):
        bitrate = mode.split('_')[1] if '_' in mode else '192'
        ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': bitrate}]})
    else:
        ydl_opts.update({'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', 'merge_output_format': 'mp4', 'postprocessor_args': ['-c:v', 'copy', '-c:a', 'aac']})

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if mode.startswith('mp3'): filename = os.path.splitext(filename)[0] + '.mp3'
            progress_data[download_id] = "Finished!"

            # Auto-cleanup memory
            def cleanup():
                time.sleep(15)
                if download_id in progress_data: del progress_data[download_id]
            threading.Thread(target=cleanup).start()

            return jsonify({'success': True, 'download_url': f'/get_file/{os.path.basename(filename)}'})
    except Exception as e:
        progress_data[download_id] = f"Error: {str(e)}"
        return jsonify({'error': str(e)}), 500

@app.route('/get_file/<filename>')
def get_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    # Get port from environment variable for Render, default to 5000
    port = int(os.environ.get('PORT', 5000))
    # MUST use host='0.0.0.0' for deployment
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
