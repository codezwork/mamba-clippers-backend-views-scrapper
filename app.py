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
            return {
                'views': info.get('view_count'),
                'likes': info.get('like_count') # NEW: Extract the like count
            }
    except Exception as e:
        print(f"Error fetching stats for {url}: {e}")
        return None

# Safe integer parsing helper
def safe_int(val):
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0

# --- NEW ROUTE: CHECK SINGLE VIDEO ---
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
    stats = get_video_stats(video_url)

    if stats is not None:
        scraped_views = stats.get('views')
        scraped_likes = stats.get('likes')
        
        try:
            # 1. Fetch the CURRENT video document from Firebase
            doc_ref = db.collection('videos').document(video_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return jsonify({"error": "Document not found in database"}), 404
                
            doc_data = doc.to_dict()
            
            # 2. Get existing views/likes (Safely parse them to integers)
            current_views = safe_int(doc_data.get('views'))
            current_likes = safe_int(doc_data.get('likes'))
            
            new_views = safe_int(scraped_views)
            
            # 3. COMPARE: Keep the highest value
            final_views = max(new_views, current_views)
            
            final_likes = None
            if scraped_likes is not None:
                new_likes = safe_int(scraped_likes)
                final_likes = max(new_likes, current_likes)

            # ---------------------------------------------------------
            # THE SMART FIX: ONLY WRITE TO FIREBASE IF NUMBERS INCREASED
            # ---------------------------------------------------------
            needs_update = False
            update_data = {}
            
            if final_views > current_views:
                update_data['views'] = final_views
                needs_update = True
                
            if final_likes is not None and final_likes > current_likes:
                update_data['likes'] = final_likes
                needs_update = True

            if needs_update:
                # Only add the timestamp if we are actually saving new numbers
                update_data['last_updated'] = firestore.SERVER_TIMESTAMP
                doc_ref.update(update_data)
                
                print(f"Update saved for {video_id}. Views: {final_views}")
                return jsonify({
                    "status": "success", 
                    "views": final_views, 
                    "likes": final_likes,
                    "note": "Database updated"
                })
            else:
                # Skip the write operation completely!
                print(f"No changes for {video_id}. Skipping database write.")
                return jsonify({
                    "status": "success", 
                    "views": current_views, 
                    "likes": current_likes,
                    "note": "Skipped write to save quota"
                })
            
        except Exception as e:
            print(f"Database error: {e}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Could not fetch views"}), 500

@app.route('/', methods=['GET'])
def health_check():
    return "Mamba Scraper is Alive!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
