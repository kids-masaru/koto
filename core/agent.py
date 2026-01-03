"""
Gemini AI Agent - handles conversation with Gemini API and tool execution
"""
import os
import sys
import json
import urllib.request

from core.prompts import SYSTEM_PROMPT, TOOLS
from utils.storage import get_user_history, add_message

# Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')


def execute_tool(tool_name, args):
    """Execute a tool and return result"""
    print(f"Executing: {tool_name}({args})", file=sys.stderr)
    
    # Import tools here to avoid circular imports
    from tools.basic_ops import calculate, calculate_date, search_and_read_pdf
    from tools.web_ops import google_web_search, fetch_url
    from tools.google_ops import (
        create_google_doc, create_google_sheet, create_google_slide,
        search_drive, list_gmail
    )
    
    if tool_name == "calculate":
        return calculate(args.get("expression", ""))
    elif tool_name == "calculate_date":
        return calculate_date(
            args.get("operation", "today"),
            args.get("days", 0),
            args.get("date_str")
        )
    elif tool_name == "search_and_read_pdf":
        return search_and_read_pdf(args.get("query", ""))
    elif tool_name == "google_web_search":
        return google_web_search(
            args.get("query", ""),
            args.get("num_results", 5)
        )
    elif tool_name == "fetch_url":
        return fetch_url(args.get("url", ""))
    elif tool_name == "create_google_doc":
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


def format_tool_result(tool_name, result):
    """Format tool result for user-friendly response"""
    if result.get("error"):
        error_msg = result['error']
        return f"ごめんなさい、エラーが出ちゃいました...😢\n{error_msg}\n\n(※もう一度試すか、言い方を変えてみてください)"
    
    # Check for execution warnings/notes (e.g. shared folder move failure)
    note = result.get("note", "")
    
    if tool_name == "calculate":
        return f"計算しました！✨\n\n{result['expression']} = **{result['result']}**"
    
    elif tool_name == "calculate_date":
        if 'time' in result:
            return f"今日は {result['date']}（{result['weekday']}）\n現在時刻: {result['time']}"
        elif 'days' in result:
            return f"{result['target']}まで **{result['days']}日** です！"
        else:
            return f"{result['date']}（{result['weekday']}）です！"
    
    elif tool_name == "search_and_read_pdf":
        text = result.get('text', '')[:1000]
        return f"PDF読み取りました！📄\n\nファイル: {result.get('filename', '')}\n\n---\n{text}"
    
    elif tool_name == "google_web_search":
        urls = result.get('urls', [])
        if not urls:
            return f"「{result.get('query', '')}」で検索しましたが、結果が見つかりませんでした〜"
        response = f"「{result.get('query', '')}」で検索しました！🔍\n\n"
        for i, url in enumerate(urls[:5], 1):
            response += f"{i}. {url}\n"
        response += "\n詳しく見たいURLがあれば教えてくださいね！"
        return response
    
    elif tool_name == "fetch_url":
        content = result.get('content', '')[:500]
        return f"Webページの内容を取得しました！🌐\n\n{content}..."
    
    elif tool_name in ["create_google_doc", "create_google_sheet", "create_google_slide"]:
        return f"作成しました！✨\n\n📄 {result.get('title', '')}\n🔗 {result['url']}{note}"
    
    elif tool_name == "search_drive":
        files = result.get("files", [])
        if not files:
            return "検索しましたが、該当するファイルは見つかりませんでした〜"
        response = f"ドライブを検索しました！{len(files)}件見つかりましたよ✨\n\n"
        for f in files[:5]:
            response += f"📁 {f['name']}\n   {f.get('webViewLink', '')}\n\n"
        return response.strip()
    
    elif tool_name == "list_gmail":
        emails = result.get("emails", [])
        if not emails:
            return "メールは見つかりませんでした〜"
        response = f"メールを確認しました！{len(emails)}件ありますよ📧\n\n"
        for e in emails[:5]:
            from_addr = e['from'][:30] + '...' if len(e['from']) > 30 else e['from']
            response += f"📩 {e['subject']}\n   From: {from_addr}\n\n"
        return response.strip()
    
    return json.dumps(result, ensure_ascii=False)


def get_gemini_response(user_id, user_message):
    """Get response from Gemini API with function calling and conversation history"""
    if not GEMINI_API_KEY:
        return "APIキーが設定されていません〜"
    
    # Add user message to history
    add_message(user_id, "user", user_message)
    
    # Get conversation history
    history = get_user_history(user_id)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    # Build conversation contents
    contents = []
    
    # Inject System Prompt
    # To avoid "User, User" sequence, we merge System Prompt into the very first message
    # OR we use the "system_instruction" feature if available (v1beta supports it but via different field)
    # For compatibility/simplicity, we'll keep the separate turn but make the model's ack invisible/internal-only logical.
    # However, to prevent "Lazy Okay", we'll instruct it strictly in the prompt.
    
    contents.append({"role": "user", "parts": [{"text": SYSTEM_PROMPT}]})
    contents.append({"role": "model", "parts": [{"text": "Understood. I will act immediately using tools without unnecessary chatter."}]})
    
    for msg in history:
        contents.append({
            "role": msg["role"] if msg["role"] == "model" else "user",
            "parts": [{"text": msg["text"]}]
        })
    
    data = {
        "contents": contents,
        "tools": [{"function_declarations": TOOLS}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 1024}
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    try:
            # Agent Loop: Handle multiple tool calls
            max_turns = 5
            for turn in range(max_turns):
                with urllib.request.urlopen(req, timeout=60) as res:
                    result = json.loads(res.read().decode('utf-8'))
                    candidates = result.get('candidates', [])
                    
                    if not candidates:
                        return 'ちょっと調子悪いみたいです...もう一度試してもらえますか？'
                    
                    content = candidates[0].get('content', {})
                    parts = content.get('parts', [])
                    
                    # 1. Check for functionCall (Prioritize over text for loop)
                    function_call_part = next((p for p in parts if 'functionCall' in p), None)
                    if function_call_part:
                        func_call = function_call_part['functionCall']
                        tool_name = func_call.get('name')
                        tool_args = func_call.get('args', {})
                        
                        print(f"[DEBUG] Executing tool: {tool_name}", file=sys.stderr)
                        tool_result = execute_tool(tool_name, tool_args)
                        
                        # Add function call and response to history (contents) for next request
                        contents.append({
                            "role": "model",
                            "parts": [function_call_part]
                        })
                        
                        contents.append({
                            "role": "function",
                            "parts": [{
                                "functionResponse": {
                                    "name": tool_name,
                                    "response": {"result": tool_result}
                                }
                            }]
                        })
                        
                        # Update request data with new history
                        data["contents"] = contents
                        req = urllib.request.Request(
                            url,
                            data=json.dumps(data).encode('utf-8'),
                            headers=headers,
                            method='POST'
                        )
                        continue # Loop to call API again with tool result

                    # 2. If no functionCall, return text (End of turn)
                    for part in parts:
                        if 'text' in part:
                            response_text = part['text']
                            add_message(user_id, "model", response_text)
                            return response_text
            
            return '考えがまとまりませんでした...もう一度聞いてください。'
    
    except Exception as e:
        print(f"Gemini error: {e}", file=sys.stderr)
        return "ちょっとエラーが出ちゃいました...😢"
