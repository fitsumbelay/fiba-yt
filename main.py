from flask import Flask, jsonify, request
import yt_dlp
from flask_cors import CORS
import math

import requests
import tempfile
import os



app = Flask(__name__, static_folder='static')
CORS(app)
ydl_opts = {'simulate': True, 'quiet': True, "get-url": True}


def convert_bytes(size):
    if size == "none" or size == None:
        return '-'
    units = ['bytes', 'KB', 'MB', 'GB', 'TB']
    for unit in units:
        if size < 1024.0:
            if unit == 'GB' or unit == 'TB':
                return f"{round(size, 1)}{unit}"
            else:
                return f"{round(size)}{unit}"
        size /= 1024.0

    return size


def sanitizeList(data):
    onlylist = ['audio_ext', 'filesize', 'format_note', 'quality', 'resolution', 'video_ext', 'url', 'audio_channels']
    sanitized_data = {key: data[key] for key in onlylist}
    # print(sanitized_data['filesize'])
    sanitized_data['filesize'] = convert_bytes(sanitized_data['filesize'])
    return sanitized_data

@app.route('/')
def index():
    return {"hello": "world"}


@app.route('/download', methods=['POST'])
def download():

    url = request.json.get('url')

    upload_url = request.json.get('upload_url')
    # print(request.json)

    # print(url, upload_url)

    if not url or not upload_url: 
        return jsonify({
            "error": "Invalid URL"
        }, 400)
    
    link = f"https://www.youtube.com/watch?v={url}"
    # Configure yt-dlp options for audio only
   
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
       
            ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                        'ffmpeg_location': os.environ.get('FFMPEG_PATH', '/usr/bin/ffmpeg')
                    }],
                    'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s')  # Use unique filename
                }
            # Create temporary directory for download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First get info without downloading
                info = ydl.extract_info(link, download=False)
                
                # Get best audio format
                best_format = get_best_audio_format(info['formats'])
                
                
                if not best_format:
                    return jsonify({
                        "error": "No suitable audio format found"
                    }), 400
                    # Update options with output template
                    # ydl_opts['outtmpl'] = )
                    
                    # Download the audio
                ydl.download(link)
                
                # Get the downloaded file path (should be only file in temp dir)
                downloaded_file = os.path.join(temp_dir, os.listdir(temp_dir)[0])

                print(downloaded_file, "temp dir")

                
                # Upload to S3
                upload_success = upload_to_s3(downloaded_file, upload_url)
                
                if not upload_success:
                    return jsonify({
                        "error": "Failed to upload to S3"
                    }), 500
                
                return jsonify({
                    "success": True,
                    "title": info["title"],
                    "thumbnail": info["thumbnail"],
                    "audio_format": sanitizeList(best_format)
                })
                
    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500



def get_best_audio_format(formats):
    """Select the best audio format based on quality metrics."""
    best_audio_format = None

    # Identify the best quality audio format available
    for f in formats:
        if f['protocol'] == "https" and f['acodec'] and f['acodec'] != 'none':
            if not best_audio_format or (f.get('abr') and f['abr'] > best_audio_format.get('abr', 0)):
                best_audio_format = f

    # Return the full format dictionary if found, else None
    print(best_audio_format, "best_audio_format")
    return sanitizeList(best_audio_format)

def sanitizeList(format_info):
    """Clean up format information."""
    return {
        "format_id": format_info.get("format_id"),
        "ext": format_info.get("ext"),
        "format": format_info.get("format"),
        "filesize": format_info.get("filesize"),
        "acodec": format_info.get("acodec"),
        "abr": format_info.get("abr")
    }

def upload_to_s3(file_path, upload_url):
    # print(upload_url, "upload url")
    """Upload file to S3 using presigned URL."""
    # print(upload_url, "upload url")
    # tempurl = "https://storage.googleapis.com/kagglesdsdata/datasets/829978/1417968/harvard.wav?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Credential=databundle-worker-v2%40kaggle-161607.iam.gserviceaccount.com%2F20241112%2Fauto%2Fstorage%2Fgoog4_request&X-Goog-Date=20241112T023539Z&X-Goog-Expires=345600&X-Goog-SignedHeaders=host&X-Goog-Signature=46a699b8b1b6571a10770127f946c4ebdf0d235e03d6d3a6e27e3949492e7ef17b5379cea7a5bc906fbcb5904c48d506f7cc45ff0a9883b2acf42f9c906e39eed93e0e819c42e5f1b2a63d9ebb7e556f7ef376f1031e9d350418e5753b34c08a404f05f9de51787565ec811e6ef1bed0333b53bbd79b153dda506c35cc6c5a02c327651f604653b20304d81b550d99273218549d0ec8bac4b8d07b8f557439b2484aebfde0890886e5bb0f4b82b50e3ea5f3fd1a312dd2473f67e47d7ed2cc228d02767c7f020f1b4e6251a16bdf5c82f330939170e70c2808d86256707ca757c66d6fc7ce8438f51a1ffa310e6d2b87f2a0464491a61e0d08f78f4e319853d3"
    with open(file_path, 'rb') as file:
        headers = {'Content-Type': 'audio/mpeg'}
        response = requests.put(upload_url, data=file, headers=headers)
        print(response.status_code)
        return response.status_code == 200

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")



