import logging
import json
from flask import jsonify

def process_chat_message(request):
    """Google Chat Incoming Webhook or HTTP Request Handler"""
    if request.method == 'GET':
        return 'Hello from Koto (Python)!', 200

    data = request.get_json(silent=True)
    if not data:
        return 'No data', 400

    logging.info(f"Received event: {json.dumps(data)}")

    original_text = "（取得失敗）"
    
    # Try standard Chat App format
    if 'message' in data and 'text' in data['message']:
        original_text = data['message']['text']
    # Try Add-on format
    elif 'chat' in data and 'messagePayload' in data['chat'] and 'message' in data['chat']['messagePayload']:
         original_text = data['chat']['messagePayload']['message'].get('text', '')

    response_text = f"【Python版】届きました！: {original_text}"

    return jsonify({
        'text': response_text
    })
