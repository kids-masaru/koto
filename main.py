from flask import Flask, request, Response
import json
import os
import sys
import hashlib
import hmac
import base64

app = Flask(__name__)

# LINE credentials (will be set via environment variables)
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')

def verify_signature(body, signature):
    """Verify LINE webhook signature"""
    if not LINE_CHANNEL_SECRET:
        return True  # Skip verification if secret not set (for testing)
    
    hash = hmac.new(
        LINE_CHANNEL_SECRET.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).digest()
    expected_signature = base64.b64encode(hash).decode('utf-8')
    return hmac.compare_digest(signature, expected_signature)

def reply_message(reply_token, text):
    """Send reply via LINE Messaging API"""
    import urllib.request
    
    url = 'https://api.line.me/v2/bot/message/reply'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
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
            print(f"Reply sent successfully: {res.status}", file=sys.stderr)
    except Exception as e:
        print(f"Reply error: {e}", file=sys.stderr)

@app.route('/', methods=['GET'])
def health_check():
    return 'Koto LINE Bot is running!', 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """LINE webhook endpoint"""
    
    # Get signature from header
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    print(f"=== LINE Webhook ===", file=sys.stderr)
    print(f"Body: {body[:200]}...", file=sys.stderr)
    
    # Verify signature
    if not verify_signature(body, signature):
        print("Invalid signature", file=sys.stderr)
        return 'Invalid signature', 400
    
    # Parse events
    try:
        data = json.loads(body)
        events = data.get('events', [])
    except Exception as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        return 'OK', 200
    
    # Process each event
    for event in events:
        event_type = event.get('type')
        print(f"Event type: {event_type}", file=sys.stderr)
        
        if event_type == 'message':
            message = event.get('message', {})
            message_type = message.get('type')
            
            if message_type == 'text':
                user_text = message.get('text', '')
                reply_token = event.get('replyToken')
                
                print(f"Received: {user_text}", file=sys.stderr)
                
                # Echo response
                response_text = f"こんにちは！「{user_text}」を受け取りました 🎉"
                
                if reply_token:
                    reply_message(reply_token, response_text)
    
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
