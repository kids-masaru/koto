import json
import sys

def process_chat_message(request):
    """Google Chat HTTP Endpoint Handler"""
    
    # Debug output
    print(f"Request method: {request.method}", file=sys.stderr)
    
    if request.method == 'GET':
        return 'Hello from Koto (Python)!', 200

    # Get JSON data
    try:
        data = request.get_json(silent=True, force=True)
        print(f"Received data: {json.dumps(data) if data else 'None'}", file=sys.stderr)
    except Exception as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        data = None
    
    if not data:
        return json.dumps({"text": "No data received"}), 200, {'Content-Type': 'application/json'}

    # Extract text from various event formats
    original_text = ""
    
    # Standard Chat App format
    if 'message' in data and 'text' in data['message']:
        original_text = data['message']['text']
    # Workspace Add-on format
    elif 'chat' in data and 'messagePayload' in data['chat']:
        msg = data['chat']['messagePayload'].get('message', {})
        original_text = msg.get('text', '')
    
    if not original_text:
        original_text = "(テキスト取得失敗)"

    response_text = f"【Python版】届きました！: {original_text}"
    
    # Return proper JSON response
    response = {"text": response_text}
    print(f"Sending response: {json.dumps(response)}", file=sys.stderr)
    
    return json.dumps(response), 200, {'Content-Type': 'application/json'}
