import json
import sys

def process_chat_message(request):
    """Google Chat HTTP Endpoint Handler"""
    
    print(f"Request method: {request.method}", file=sys.stderr)
    
    if request.method == 'GET':
        return 'Hello from Koto (Python)!', 200

    # Get JSON data
    try:
        data = request.get_json(silent=True, force=True)
        print(f"Received data: {json.dumps(data) if data else 'None'}", file=sys.stderr)
    except Exception as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        return {"text": "Error parsing request"}

    if not data:
        return {"text": "No data received"}

    # Extract text from Workspace Add-on format (chat.messagePayload.message.text)
    original_text = ""
    
    if 'chat' in data and 'messagePayload' in data['chat']:
        msg = data['chat']['messagePayload'].get('message', {})
        original_text = msg.get('text', '')
    # Fallback: Standard Chat App format
    elif 'message' in data and 'text' in data['message']:
        original_text = data['message']['text']
    
    if not original_text:
        original_text = "(テキスト取得失敗)"

    response_text = f"【Koto】届きました！: {original_text}"
    
    print(f"Sending response: {response_text}", file=sys.stderr)
    
    # Return dict directly - functions-framework will serialize to JSON
    return {"text": response_text}
