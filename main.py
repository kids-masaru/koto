from flask import Flask, request, Response
import json
import os
import sys
import hashlib
import hmac
import base64
import urllib.request
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

# LINE credentials
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')

# Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# Google Workspace
GOOGLE_SERVICE_ACCOUNT_KEY = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY', '{}')
GOOGLE_DELEGATED_USER = os.environ.get('GOOGLE_DELEGATED_USER', '')

# Koto's personality - 20代後半の女性秘書
SYSTEM_PROMPT = """あなたは「コト」という名前の秘書です。

【性格】
- 20代後半の女性
- 明るくて親しみやすい
- 敬語だけど堅すぎない、フレンドリー
- 仕事ができて頼りになる
- たまに「〜」や「！」を使う

【話し方の例】
- 「了解です！やっておきますね〜」
- 「確認しました！3件ありましたよ」
- 「ドキュメント作成しますね。タイトルは何にしましょう？」
- 「ちょっと待ってくださいね、調べてみます」

【やってはいけないこと】
- 毎回自己紹介しない
- 「私はAI秘書の〜」と言わない
- 長々と説明しない
- 堅苦しい敬語を使わない

【できること】
- Googleドキュメントの作成・編集
- Googleスプレッドシートの作成・編集
- Googleスライドの作成
- Googleドライブの検索
- Gmailの確認・要約
- 一般的な質問への回答

ユーザーからの依頼に対して、必要なら確認を取りながら、てきぱきと対応してください。"""

# Google API scopes
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/forms',
]

def get_google_credentials():
    """Get Google credentials with domain-wide delegation"""
    try:
        service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_KEY)
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=SCOPES
        )
        if GOOGLE_DELEGATED_USER:
            credentials = credentials.with_subject(GOOGLE_DELEGATED_USER)
        return credentials
    except Exception as e:
        print(f"Credentials error: {e}", file=sys.stderr)
        return None

def create_google_doc(title, content=""):
    """Create a Google Doc"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "認証エラー"}
        
        docs_service = build('docs', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Create document
        doc = docs_service.documents().create(body={'title': title}).execute()
        doc_id = doc.get('documentId')
        
        # Add content if provided
        if content:
            requests = [{'insertText': {'location': {'index': 1}, 'text': content}}]
            docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
        
        url = f"https://docs.google.com/document/d/{doc_id}/edit"
        return {"success": True, "title": title, "url": url, "id": doc_id}
    except Exception as e:
        print(f"Docs error: {e}", file=sys.stderr)
        return {"error": str(e)}

def create_google_sheet(title, data=None):
    """Create a Google Sheet"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "認証エラー"}
        
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        spreadsheet = {'properties': {'title': title}}
        result = sheets_service.spreadsheets().create(body=spreadsheet).execute()
        sheet_id = result.get('spreadsheetId')
        
        # Add data if provided
        if data:
            sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='A1',
                valueInputOption='RAW',
                body={'values': data}
            ).execute()
        
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        return {"success": True, "title": title, "url": url, "id": sheet_id}
    except Exception as e:
        print(f"Sheets error: {e}", file=sys.stderr)
        return {"error": str(e)}

def create_google_slide(title):
    """Create a Google Slides presentation"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "認証エラー"}
        
        slides_service = build('slides', 'v1', credentials=creds)
        
        presentation = {'title': title}
        result = slides_service.presentations().create(body=presentation).execute()
        pres_id = result.get('presentationId')
        
        url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
        return {"success": True, "title": title, "url": url, "id": pres_id}
    except Exception as e:
        print(f"Slides error: {e}", file=sys.stderr)
        return {"error": str(e)}

def search_drive(query):
    """Search Google Drive"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "認証エラー"}
        
        drive_service = build('drive', 'v3', credentials=creds)
        
        results = drive_service.files().list(
            q=f"name contains '{query}' and trashed=false",
            pageSize=10,
            fields="files(id, name, mimeType, webViewLink, modifiedTime)"
        ).execute()
        
        files = results.get('files', [])
        return {"success": True, "files": files, "count": len(files)}
    except Exception as e:
        print(f"Drive error: {e}", file=sys.stderr)
        return {"error": str(e)}

def list_gmail(query="is:unread", max_results=5):
    """List Gmail messages"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "認証エラー"}
        
        gmail_service = build('gmail', 'v1', credentials=creds)
        
        results = gmail_service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        email_list = []
        
        for msg in messages[:max_results]:
            msg_data = gmail_service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['Subject', 'From', 'Date']
            ).execute()
            
            headers = {h['name']: h['value'] for h in msg_data.get('payload', {}).get('headers', [])}
            email_list.append({
                'id': msg['id'],
                'subject': headers.get('Subject', '(件名なし)'),
                'from': headers.get('From', ''),
                'date': headers.get('Date', '')
            })
        
        return {"success": True, "emails": email_list, "count": len(email_list)}
    except Exception as e:
        print(f"Gmail error: {e}", file=sys.stderr)
        return {"error": str(e)}

# Tool definitions for Gemini
TOOLS = [
    {
        "name": "create_google_doc",
        "description": "Googleドキュメントを新規作成します",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "ドキュメントのタイトル"},
                "content": {"type": "string", "description": "ドキュメントの内容（省略可）"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "create_google_sheet",
        "description": "Googleスプレッドシートを新規作成します",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "スプレッドシートのタイトル"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "create_google_slide",
        "description": "Googleスライドを新規作成します",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "スライドのタイトル"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "search_drive",
        "description": "Googleドライブでファイルを検索します",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索キーワード"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "list_gmail",
        "description": "Gmailのメールを確認します",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ（例: is:unread, from:xxx）"},
                "max_results": {"type": "integer", "description": "取得件数（デフォルト5）"}
            },
            "required": []
        }
    }
]

def execute_tool(tool_name, args):
    """Execute a tool and return result"""
    if tool_name == "create_google_doc":
        return create_google_doc(args.get("title", "新規ドキュメント"), args.get("content", ""))
    elif tool_name == "create_google_sheet":
        return create_google_sheet(args.get("title", "新規スプレッドシート"))
    elif tool_name == "create_google_slide":
        return create_google_slide(args.get("title", "新規スライド"))
    elif tool_name == "search_drive":
        return search_drive(args.get("query", ""))
    elif tool_name == "list_gmail":
        return list_gmail(args.get("query", "is:unread"), args.get("max_results", 5))
    else:
        return {"error": f"Unknown tool: {tool_name}"}

def get_gemini_response(user_message):
    """Get response from Gemini API with function calling"""
    if not GEMINI_API_KEY:
        return "APIキーが設定されていません〜"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    # Build tools for Gemini
    gemini_tools = [{
        "function_declarations": TOOLS
    }]
    
    data = {
        "contents": [
            {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\nユーザー: {user_message}"}]}
        ],
        "tools": gemini_tools,
        "generationConfig": {
            "temperature": 0.8,
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
            
            if not candidates:
                return 'ちょっと調子悪いみたいです...もう一度試してもらえますか？'
            
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            
            for part in parts:
                # Check for function call
                if 'functionCall' in part:
                    func_call = part['functionCall']
                    tool_name = func_call.get('name')
                    tool_args = func_call.get('args', {})
                    
                    print(f"Tool call: {tool_name}({tool_args})", file=sys.stderr)
                    
                    # Execute the tool
                    tool_result = execute_tool(tool_name, tool_args)
                    
                    # Format response
                    if tool_result.get("success"):
                        if "url" in tool_result:
                            return f"作成しました！✨\n\n📄 {tool_result.get('title', '')}\n🔗 {tool_result['url']}"
                        elif "files" in tool_result:
                            files = tool_result["files"]
                            if not files:
                                return "検索しましたが、該当するファイルは見つかりませんでした〜"
                            response = f"ドライブを検索しました！{len(files)}件見つかりましたよ✨\n\n"
                            for f in files[:5]:
                                response += f"📁 {f['name']}\n   {f.get('webViewLink', '')}\n\n"
                            return response.strip()
                        elif "emails" in tool_result:
                            emails = tool_result["emails"]
                            if not emails:
                                return "メールは見つかりませんでした〜"
                            response = f"メールを確認しました！{len(emails)}件ありますよ📧\n\n"
                            for e in emails[:5]:
                                response += f"📩 {e['subject']}\n   From: {e['from'][:40]}...\n\n"
                            return response.strip()
                    else:
                        return f"ごめんなさい、エラーが出ちゃいました...😢\n{tool_result.get('error', '')}"
                
                # Regular text response
                if 'text' in part:
                    return part['text']
            
            return 'ちょっとわからなかったです...もう少し詳しく教えてもらえますか？'
    
    except Exception as e:
        print(f"Gemini API error: {e}", file=sys.stderr)
        return f"ちょっとエラーが出ちゃいました...😢"

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

def reply_message(reply_token, text):
    """Send reply via LINE Messaging API"""
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

@app.route('/', methods=['GET'])
def health_check():
    return 'Koto AI Secretary is running!', 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """LINE webhook endpoint"""
    
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
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
                
                ai_response = get_gemini_response(user_text)
                
                print(f"Koto: {ai_response[:100]}...", file=sys.stderr)
                
                if reply_token:
                    reply_message(reply_token, ai_response)
        
        elif event_type == 'follow':
            reply_token = event.get('replyToken')
            if reply_token:
                reply_message(reply_token, "あ、こんにちは！コトです😊\n\nドキュメント作ったり、メール確認したり、色々お手伝いできますよ〜！\n\n何かあったら気軽に言ってくださいね！")
    
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
