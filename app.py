import os
import json
import yt_dlp
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- 1. SETUP FIREBASE ---
# Initialize DB variable to None globally for safety
db = None

# Get the JSON string from the environment variable
firebase_creds_str = os.environ.get('FIREBASE_CREDENTIALS')

if firebase_creds_str:
    try:
        # Parse the string into a Python dictionary
        creds_dict = json.loads(firebase_creds_str)

        # --- THE CRITICAL FIX --- 
        # Render sometimes escapes the '\n' characters in the private key.
        # We manually replace literal "\n" strings with actual newlines.
        if 'private_key' in creds_dict:
            creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')

        # Initialize the app with the fixed credentials
        cred = credentials.Certificate(creds_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase initialized successfully!")
        
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
else:
    print("Warning: FIREBASE_CREDENTIALS environment variable not found.")


# --- 2. HELPER FUNCTION ---
def get_video_stats(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        # 'proxy': 'http://user:pass@host:port',  # Uncomment this line later if you buy proxies!
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('view_count')
    except Exception as e:
        print(f"Error fetching stats for {url}: {e}")
        return None

# --- 3. ROUTES ---
@app.route('/refresh-stats', methods=['POST'])
def refresh_stats():
    # Safety check: Ensure DB is connected
    if not db:
        return jsonify({"error": "Database not initialized. Check server logs."}), 500

    videos_ref = db.collection('videos')
    docs = videos_ref.stream()

    updated_count = 0

    for doc in docs:
        video_data = doc.to_dict()
        video_id = doc.id
        video_url = video_data.get('link')

        if video_url:
            print(f"Checking: {video_data.get('title', 'Unknown')}...")
            
            # Fetch views from TikTok/IG
            views = get_video_stats(video_url)

            if views is not None:
                # Update Firebase
                videos_ref.document(video_id).update({
                    'views': views,
                    'last_updated': firestore.SERVER_TIMESTAMP
                })
                updated_count += 1
            else:
                print(f"Skipping update for {video_id} (could not fetch views)")

    return jsonify({"status": "success", "updated": updated_count})

@app.route('/', methods=['GET'])
def health_check():
    return "Mamba Scraper is Alive!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
