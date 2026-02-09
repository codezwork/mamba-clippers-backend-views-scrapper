import os
import json
import yt_dlp
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- SETUP FIREBASE ---
db = None
firebase_creds_str = os.environ.get('FIREBASE_CREDENTIALS')

if firebase_creds_str:
    try:
        creds_dict = json.loads(firebase_creds_str)
        if 'private_key' in creds_dict:
            creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        cred = credentials.Certificate(creds_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase initialized successfully!")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")

# --- HELPER FUNCTION ---
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
        print(f"Error fetching stats for {url}: {e}")
        return None

# --- NEW ROUTE: CHECK SINGLE VIDEO ---
@app.route('/check-video', methods=['POST'])
def check_video():
    if not db:
        return jsonify({"error": "Database not initialized"}), 500

    data = request.json
    video_url = data.get('url')
    video_id = data.get('id')

    if not video_url or not video_id:
        return jsonify({"error": "Missing URL or ID"}), 400

    print(f"Checking single video: {video_url}...")
    views = get_video_stats(video_url)

    if views is not None:
        # Update specific document in Firestore
        try:
            db.collection('videos').document(video_id).update({
                'views': views,
                'last_updated': firestore.SERVER_TIMESTAMP
            })
            return jsonify({"status": "success", "views": views})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Could not fetch views"}), 500

@app.route('/', methods=['GET'])
def health_check():
    return "Mamba Scraper is Alive!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
