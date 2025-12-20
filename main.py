from flask import Flask, request, Response
import json
import os
import sys
import hashlib
import hmac
import base64
import urllib.request

app = Flask(__name__)

# LINE credentials
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')

# Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# System prompt for Koto
SYSTEM_PROMPT = """あなたは「Koto（コト）」という名前のAI秘書です。
ユーザーの仕事をサポートするために、親切で丁寧な対応を心がけてください。
日本語で会話してください。
簡潔で分かりやすい回答を心がけてください。"""

def verify_signature(body, signature):
    """Verify LINE webhook signature"""
    if not LINE_CHANNEL_SECRET:
        return True
    
    hash = hmac.new(
        LINE_CHANNEL_SECRET.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).digest()
    expected_signature = base64.b64encode(hash).decode('utf-8')
    return hmac.compare_digest(signature, expected_signature)

def get_gemini_response(user_message):
    """Get response from Gemini API"""
    if not GEMINI_API_KEY:
        return "Gemini API キーが設定されていません。"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    data = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{SYSTEM_PROMPT}\n\nユーザー: {user_message}"}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            result = json.loads(res.read().decode('utf-8'))
            candidates = result.get('candidates', [])
            if candidates:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if parts:
                    return parts[0].get('text', 'レスポンスを取得できませんでした。')
            return 'レスポンスを取得できませんでした。'
    except Exception as e:
        print(f"Gemini API error: {e}", file=sys.stderr)
        return f"エラーが発生しました: {str(e)}"

def reply_message(reply_token, text):
    """Send reply via LINE Messaging API"""
    url = 'https://api.line.me/v2/bot/message/reply'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    
    # LINE has a 5000 character limit per message
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

@app.route('/', methods=['GET'])
def health_check():
    return 'Koto AI Secretary is running!', 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """LINE webhook endpoint"""
    
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    print(f"=== LINE Webhook ===", file=sys.stderr)
    
    if not verify_signature(body, signature):
        return 'Invalid signature', 400
    
    try:
        data = json.loads(body)
        events = data.get('events', [])
    except Exception as e:
        print(f"JSON error: {e}", file=sys.stderr)
        return 'OK', 200
    
    for event in events:
        event_type = event.get('type')
        
        if event_type == 'message':
            message = event.get('message', {})
            message_type = message.get('type')
            
            if message_type == 'text':
                user_text = message.get('text', '')
                reply_token = event.get('replyToken')
                
                print(f"User: {user_text}", file=sys.stderr)
                
                # Get AI response
                ai_response = get_gemini_response(user_text)
                
                print(f"Koto: {ai_response[:100]}...", file=sys.stderr)
                
                if reply_token:
                    reply_message(reply_token, ai_response)
        
        elif event_type == 'follow':
            # User added the bot
            reply_token = event.get('replyToken')
            if reply_token:
                reply_message(reply_token, "はじめまして！Koto（コト）です 🎉\nあなたのAI秘書として、お手伝いします！\n\n何でも聞いてくださいね！")
    
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
