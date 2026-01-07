"""
Koto AI Secretary - LINE Bot Entry Point
Flask server with asynchronous message processing and Config API
"""
import os
import sys
import json
import hashlib
import hmac
import base64
import urllib.request
import threading
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent import get_gemini_response
from utils.storage import clear_user_history
from utils.sheets_config import load_config, save_config
from tools.google_ops import search_drive
from flask_cors import CORS

app = Flask(__name__)
# Enable CORS for dashboard - allow all origins and handle preflight
CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})


@app.route('/')
def healthcheck():
    """Health check endpoint for Railway/deployment platforms"""
    return 'KOTO is running!', 200


@app.route('/debug/vector-status')
def vector_status():
    """Debug endpoint to check vector store status"""
    import json
    try:
        from utils.vector_store import get_collection_stats
        stats = get_collection_stats()
        return json.dumps(stats, ensure_ascii=False), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, {'Content-Type': 'application/json'}


# LINE credentials
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')


def verify_signature(body, signature):
    """Verify LINE webhook signature"""
    if not LINE_CHANNEL_SECRET:
        return True
    hash_value = hmac.new(
        LINE_CHANNEL_SECRET.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return hmac.compare_digest(signature, base64.b64encode(hash_value).decode('utf-8'))


def push_message(user_id, texts):
    """Send message via LINE Push API (for async responses)
       texts: string or list of strings
    """
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    
    # Normalize to list
    if isinstance(texts, str):
        texts = [texts]
        
    messages = []
    for text in texts:
        # Truncate if too long
        if len(text) > 4500:
            text = text[:4500] + "..."
        messages.append({'type': 'text', 'text': text})
    
    # Send in chunks of 5 (LINE API limit)
    for i in range(0, len(messages), 5):
        chunk = messages[i:i+5]
        
        data = {
            'to': user_id,
            'messages': chunk
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        try:
            with urllib.request.urlopen(req) as res:
                print(f"Push sent to {user_id[:8]}: {res.status}", file=sys.stderr)
        except Exception as e:
            print(f"Push error: {e}", file=sys.stderr)


def reply_message(reply_token, text):
    """Send message via LINE Reply API (for sync responses)"""
    url = 'https://api.line.me/v2/bot/message/reply'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    
    if len(text) > 4500:
        text = text[:4500] + "..."
    
    data = {
        'replyToken': reply_token,
        'messages': [{'type': 'text', 'text': text}]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req) as res:
            print(f"Reply sent: {res.status}", file=sys.stderr)
    except Exception as e:
        print(f"Reply error: {e}", file=sys.stderr)


def process_message_async(user_id, user_text, reply_token=None):
    """Process message in background and send response via Reply/Push API"""
    try:
        print(f"Processing message from {user_id[:8]}: {user_text}", file=sys.stderr)
        
        ai_response = get_gemini_response(user_id, user_text)
        
        print(f"Koto response: {ai_response[:100]}...", file=sys.stderr)
        
        # Try Reply API first (Free, but token expires in ~30s)
        success = False
        if reply_token:
            try:
                reply_message(reply_token, ai_response)
                success = True
            except Exception as e:
                print(f"Reply failed (likely timeout), trying Push: {e}", file=sys.stderr)
        
        # Fallback to Push API (Quota limited)
        if not success:
            push_message(user_id, ai_response)
            
    except Exception as e:
        print(f"Async processing error: {e}", file=sys.stderr)
        # Try to send error message
        try:
            if reply_token:
                reply_message(reply_token, "ごめんなさい、エラーが出ちゃいました...😢\nもう一度試してもらえますか？")
            else:
                push_message(user_id, "ごめんなさい、エラーが出ちゃいました...😢\nもう一度試してもらえますか？")
        except Exception:
            pass


@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return 'Koto AI Secretary is running!', 200


@app.route('/webhook', methods=['POST'])
def webhook():
    """LINE webhook endpoint - returns immediately, processes async"""
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    if not verify_signature(body, signature):
        return 'Invalid signature', 400
    
    try:
        data = json.loads(body)
        events = data.get('events', [])
    except Exception:
        return 'OK', 200
    
    for event in events:
        event_type = event.get('type')
        source = event.get('source', {})
        user_id = source.get('userId', 'unknown')
        
        if event_type == 'message':
            message = event.get('message', {})
            message_type = message.get('type')
            
            if message_type == 'text':
                user_text = message.get('text', '')
                reply_token = event.get('replyToken')
                
                print(f"User [{user_id[:8]}]: {user_text}", file=sys.stderr)
                
            if message_type == 'text':
                user_text = message.get('text', '')
                reply_token = event.get('replyToken')
                
                print(f"User [{user_id[:8]}]: {user_text}", file=sys.stderr)
                
                # Process synchronously (Vercel/Serverless does not support background threads after response)
                process_message_async(user_id, user_text, reply_token)
        
        elif event_type == 'follow':
            reply_token = event.get('replyToken')
            clear_user_history(user_id)
            if reply_token:
                reply_message(
                    reply_token,
                    "あ、こんにちは！コトです😊\n\n"
                    "色々お手伝いできますよ〜！\n"
                    "・ドキュメント作成\n"
                    "・メール確認\n"
                    "・計算\n"
                    "・PDF読み取り\n"
                    "・Web検索\n\n"
                    "気軽に言ってくださいね！"
                )
    
    # Return immediately - processing happens in background
    return 'OK', 200

@app.route('/cron', methods=['GET'])
def cron_job():
    """Daily Cron Job - Send Morning Updates"""
    # Verify Cron Secret
    cron_secret = os.environ.get('CRON_SECRET')
    auth_header = request.headers.get('Authorization')
    
    if cron_secret and (not auth_header or auth_header != f"Bearer {cron_secret}"):
        return 'Unauthorized', 401
    
    from utils.user_db import get_active_users
    
    users = get_active_users()
    print(f"Cron started. Users to notify: {len(users)}", file=sys.stderr)
    
    for user in users:
        user_id = user['user_id']
        location = user['location']
        
        # Load user-specific config (or global config for now)
        user_config = load_config()
        
        # Get reminders array (new format) or fallback to old format
        reminders = user_config.get('reminders', [])
        
        # Fallback: if no reminders but old format exists, convert it
        if not reminders and user_config.get('reminder_time'):
            reminders = [{
                'name': '朝のリマインダー',
                'time': user_config.get('reminder_time', '07:00'),
                'prompt': user_config.get('reminder_prompt', '今日の天気と予定を教えて'),
                'enabled': True
            }]
        
        # Get current time in JST
        from datetime import datetime, timezone, timedelta
        jst = timezone(timedelta(hours=9))
        now = datetime.now(jst)
        current_hour = now.hour
        
        # Determine which reminders should fire based on current hour
        # We check if the reminder time's hour matches current hour
        for reminder in reminders:
            if not reminder.get('enabled', True):
                continue
            
            reminder_time = reminder.get('time', '07:00')
            try:
                reminder_hour = int(reminder_time.split(':')[0])
            except:
                reminder_hour = 7
            
            # Check if this reminder should fire now (within the same hour)
            if reminder_hour != current_hour:
                continue
            
            base_prompt = reminder.get('prompt', '今日の天気と予定を教えて')
            
            # Build prompt with location and formatting instructions
            prompt = (
                f"今日の{location}の{base_prompt}\n"
                "【重要】以下の3つのセクションに分けて、それぞれの間に「@@@」という区切り文字を入れて出力してください。\n"
                "1. 天気に関する情報\n"
                "2. スケジュール・タスクに関する情報\n"
                "3. 気の利いた一言メッセージ"
            )
            print(f"Generating report for {user_id[:8]} ({location}) - {reminder.get('name', 'Reminder')}...", file=sys.stderr)
        
            try:
                # Use get_gemini_response directly to leverage existing tool logic
                response = get_gemini_response(user_id, prompt)
                
                # Split response by delimiter
                messages = [msg.strip() for msg in response.split('@@@') if msg.strip()]
                
                # Add greeting to the first message if not present
                if messages:
                    if current_hour < 12 and "おはよう" not in messages[0]:
                        messages[0] = f"おはようございます！☀️\n\n{messages[0]}"
                    elif current_hour >= 18 and "こんばんは" not in messages[0]:
                        messages[0] = f"こんばんは！🌙\n\n{messages[0]}"
                else:
                    # Fallback if split fails
                    messages = [response]
                
                push_message(user_id, messages)
                print(f"Sent report to {user_id[:8]} ({reminder.get('name', 'Reminder')})", file=sys.stderr)
            except Exception as e:
                print(f"Error processing user {user_id[:8]}: {e}", file=sys.stderr)
            
    return f'Processed {len(users)} users', 200


@app.route('/api/config', methods=['GET', 'POST', 'OPTIONS'])
def handle_config():
    """Get or update configuration"""
    # Handle preflight request
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    if request.method == 'GET':
        return json.dumps(load_config(), ensure_ascii=False), 200, {'Content-Type': 'application/json'}
    
    elif request.method == 'POST':
        try:
            new_config = request.json
            if save_config(new_config):
                return json.dumps({"success": True, "config": new_config}), 200, {'Content-Type': 'application/json'}
            else:
                return json.dumps({"error": "Failed to save config"}), 500, {'Content-Type': 'application/json'}
        except Exception as e:
            return json.dumps({"error": str(e)}), 400, {'Content-Type': 'application/json'}

@app.route('/api/folders', methods=['GET', 'OPTIONS'])
def list_folders():
    """List Google Drive folders for selection (Navigation support)"""
    # Handle preflight request
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    query = request.args.get('q', '')
    parent_id = request.args.get('parentId')
    
    try:
        from utils.auth import get_google_credentials
        from googleapiclient.discovery import build
        
        creds = get_google_credentials()
        if not creds:
             return json.dumps({"error": "Auth failed"}), 401, {'Content-Type': 'application/json'}
             
        service = build('drive', 'v3', credentials=creds)
        
        # Base filter: folders only, not trashed
        q_filter = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        
        if parent_id:
            # Navigate into specific folder
            q_filter += f" and '{parent_id}' in parents"
        elif query:
            # Search mode (global)
            # Escape single quotes
            safe_query = query.replace("'", "\\'")
            q_filter += f" and name contains '{safe_query}'"
        else:
            # Default: Root folder
            q_filter += " and 'root' in parents"
            
        results = service.files().list(
            q=q_filter,
            pageSize=50,
            fields="files(id, name)",
            orderBy="folder,name",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute()
        
        folders = results.get('files', [])
        return json.dumps({"folders": folders}), 200, {'Content-Type': 'application/json'}
        
    except Exception as e:
        return json.dumps({"error": str(e)}), 500, {'Content-Type': 'application/json'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting Koto AI Secretary on port {port}...", file=sys.stderr)
    app.run(host='0.0.0.0', port=port)
