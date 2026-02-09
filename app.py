import os
import json
import yt_dlp
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
# Allow requests from any origin for now (easier for testing), or restrict to your Vercel domain later
CORS(app) 

# Initialize Firebase using Environment Variable
firebase_creds = os.environ.get('FIREBASE_CREDENTIALS')
if firebase_creds:
    # Render stores newlines as literal "\n" strings, so we must replace them
    creds_dict = json.loads(firebase_creds)
    cred = credentials.Certificate(creds_dict)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    print("Warning: FIREBASE_CREDENTIALS not found.")

def get_video_stats(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('view_count')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

@app.route('/refresh-stats', methods=['POST'])
def refresh_stats():
    if not firebase_creds:
         return jsonify({"error": "Firebase credentials not configured"}), 500

    videos_ref = db.collection('videos')
    docs = videos_ref.stream()

    updated_count = 0

    for doc in docs:
        video_data = doc.to_dict()
        video_id = doc.id
        video_url = video_data.get('link')

        if video_url:
            print(f"Checking: {video_data.get('title', 'Unknown')}...")
            views = get_video_stats(video_url)

            if views is not None:
                videos_ref.document(video_id).update({
                    'views': views,
                    'last_updated': firestore.SERVER_TIMESTAMP
                })
                updated_count += 1

    return jsonify({"status": "success", "updated": updated_count})

@app.route('/', methods=['GET'])
def health_check():
    return "Mamba Scraper is Alive!", 200

if __name__ == '__main__':
    # Render assigns a port automatically in the PORT environment variable
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
