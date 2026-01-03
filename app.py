"""
Koto AI Secretary - LINE Bot Entry Point
Flask server with asynchronous message processing
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

app = Flask(__name__)

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


def push_message(user_id, text):
    """Send message via LINE Push API (for async responses)"""
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    
    # Truncate if too long
    if len(text) > 4500:
        text = text[:4500] + "..."
    
    data = {
        'to': user_id,
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting Koto AI Secretary on port {port}...", file=sys.stderr)
    app.run(host='0.0.0.0', port=port)
