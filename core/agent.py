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


def execute_tool(tool_name, args, user_id=None):
    """Execute a tool and return result"""
    print(f"Executing: {tool_name}({args})", file=sys.stderr)
    
    # Import tools here to avoid circular imports
    from tools.basic_ops import calculate, calculate_date, search_and_read_pdf
    from tools.web_ops import google_web_search, fetch_url
    from tools.google_ops import (
        create_google_doc, create_google_sheet, create_google_slide,
        search_drive, list_gmail, get_gmail_body,
        list_calendar_events, create_calendar_event,
        list_tasks, add_task
    )
    from utils.user_db import register_user
    
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
    elif tool_name == "get_gmail_body":
        return get_gmail_body(args.get("message_id", ""))
    elif tool_name == "set_reminder":
        if not user_id:
            return {"error": "ユーザーIDが取得できませんでした。"}
        return register_user(user_id, args.get("location", ""))
    elif tool_name == "list_calendar_events":
        return list_calendar_events(
            args.get("query"),
            args.get("time_min"),
            args.get("time_max")
        )
    elif tool_name == "create_calendar_event":
        return create_calendar_event(
            args.get("summary"),
            args.get("start_time"),
            args.get("end_time"),
            args.get("location")
        )
    elif tool_name == "list_tasks":
        return list_tasks(args.get("show_completed", False), args.get("due_date"))
    elif tool_name == "add_task":
        return add_task(args.get("title"), args.get("due_date"))
    elif tool_name == "list_notion_tasks":
        from tools.notion_ops import list_notion_tasks
        # Get database_id from args or from config
        database_id = args.get("database_id", "")
        if not database_id:
            from utils.sheets_config import load_config
            config = load_config()
            notion_dbs = config.get("notion_databases", [])
            if notion_dbs:
                database_id = notion_dbs[0].get("id", "")
        return list_notion_tasks(database_id, args.get("filter_today", False))
    elif tool_name == "create_notion_task":
        from tools.notion_ops import create_notion_task
        # Get database_id from args or from config
        database_id = args.get("database_id", "")
        if not database_id:
            from utils.sheets_config import load_config
            config = load_config()
            notion_dbs = config.get("notion_databases", [])
            if notion_dbs:
                database_id = notion_dbs[0].get("id", "")
        return create_notion_task(database_id, args.get("title", ""), args.get("due_date"), args.get("status"))
    elif tool_name == "delegate_to_maker":
        from core.maker import maker
        response_text = maker.run(args.get("request", ""))
        return {"report": response_text}
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
            snippet = e.get('snippet', '')[:50]
            response += f"📩 {e['subject']}\n   From: {from_addr}\n   {snippet}...\n\n"
        return response.strip()

    elif tool_name == "get_gmail_body":
        if result.get("error"):
            return f"メール取得エラー: {result['error']}"
        subject = result.get("subject", "(件名なし)")
        body = result.get("body", "")[:500]
        return f"📧 {subject}\n---\n{body}"
    elif tool_name == "set_reminder":
        return f"リマインダー設定しました！✨\n毎日朝7時頃に「{result.get('location', '')}」の天気と服装をお知らせしますね！☀️"
    
    elif tool_name == "list_calendar_events":
        events = result.get("events", [])
        if not events:
            return "予定は見つかりませんでした〜"
        
        response = f"予定を確認しました！{len(events)}件あります📅\n\n"
        for evt in events[:5]:
            start = evt['start'].get('dateTime', evt['start'].get('date'))
            summary = evt.get('summary', '(タイトルなし)')
            response += f"🗓️ {start[:16].replace('T', ' ')}\n   {summary}\n\n"
        return response.strip()

    elif tool_name == "create_calendar_event":
        link = result.get("link", "")
        return f"予定を追加しました！✨\n\n📅 {result.get('event', {}).get('summary', '')}\n🔗 {link}"
    
    elif tool_name == "list_tasks":
        tasks = result.get("tasks", [])
        if not tasks:
            return "ToDoリストはありませんでした〜"
        response = f"ToDoを確認しました！{len(tasks)}件あります📝\n\n"
        for t in tasks[:10]:
            title = t['title']
            due = f" (期限: {t['due'][:10]})" if 'due' in t else ""
            response += f"☐ {title}{due}\n"
        return response.strip()

    elif tool_name == "add_task":
        t = result.get("task", {})
        return f"ToDoを追加しました！✨\n\n📝 {t.get('title', '')}"

    elif tool_name == "delegate_to_maker":
        return f"Make Agentにお願いしてきました！👩‍💻\n\n{result.get('report', '')}"
    
    return json.dumps(result, ensure_ascii=False)


def get_gemini_response(user_id, user_message, image_data=None, mime_type=None):
    """Get response from Gemini API with function calling and conversation history"""
    if not GEMINI_API_KEY:
        return "APIキーが設定されていません〜"
    
    # Add user message to history
    # If image is present, we only log [Image] marker in text history for now
    log_message = user_message
    if image_data:
        log_message += " [添付画像あり]"
    add_message(user_id, "user", log_message)
    
    # Get conversation history
    history = get_user_history(user_id)
    
    # Use gemini-2.0-flash-exp (or gemini-1.5-pro) for Multimodal
    # gemini-3-flash-preview is also capable
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    # Build dynamic system prompt with config-based customizations
    from utils.sheets_config import load_config
    try:
        config = load_config()
    except:
        config = {}
    
    # Build knowledge context
    knowledge_context = ""
    knowledge_sources = config.get('knowledge_sources', [])
    if knowledge_sources:
        knowledge_context = "\n\n【★ナレッジフォルダ★】\n以下のフォルダがナレッジベースとして設定されています。ユーザーの質問に関連するフォルダがあれば、search_driveでそのフォルダ内を検索してください。\n"
        for ks in knowledge_sources:
            knowledge_context += f"- フォルダ名: {ks.get('name', '不明')} (ID: {ks.get('id', '')}) → {ks.get('instruction', '関連する質問に答える')}\n"
    
    # Get master prompt if set
    master_prompt = config.get('master_prompt', '')
    master_prompt_section = ""
    if master_prompt.strip():
        master_prompt_section = f"\n\n【★マスタープロンプト（詳細な動作指示）★】\n{master_prompt}\n"
    
    # Get personality customization
    personality = config.get('personality', '')
    personality_section = ""
    if personality.strip():
        personality_section = f"あなたの性格: {personality}\n"
        
    # [Diff] Fetch User Profile (Phase 5)
    from utils.vector_store import get_user_profile
    user_profile = get_user_profile(user_id)
    profile_section = ""
    if user_profile and isinstance(user_profile, dict):
        profile_section = f"""
【★ユーザープロファイル（重要：あなたが知っているユーザー情報）★】
名前: {user_profile.get('name', '不明')}
性格・特徴: {', '.join(user_profile.get('personality_traits', []))}
興味・関心: {', '.join(user_profile.get('interests', []))}
価値観: {', '.join(user_profile.get('values', []))}
現在の目標: {', '.join(user_profile.get('current_goals', []))}
要約: {user_profile.get('summary', '')}

あなたは、上記のプロファイルに基づき、ユーザー（{user_profile.get('name', 'ユーザー')}さん）を深く理解している秘書として振る舞ってください。
"""
        personality_section = f"\n\n【★性格設定★】\n以下の性格・話し方でユーザーに接してください：\n{personality}\n"
    
    # Get user name for personalization
    user_name = config.get('user_name', '')
    user_name_section = ""
    if user_name.strip():
        user_name_section = f"\n\n【★ユーザー名★】\nあなたが仕えている人の名前は「{user_name}」です。親しみを込めて接してください。\n"
    
    # RAG: Retrieve relevant past conversations
    rag_context = ""
    try:
        from utils.vector_store import get_context_summary, save_conversation
        rag_context = get_context_summary(user_id, user_message, max_tokens=300)
        # Save user message to vector store
        save_conversation(user_id, "user", user_message)
    except Exception as e:
        print(f"RAG context error: {e}", file=sys.stderr)
    
    # Combine prompts with RAG and Profile context
    full_system_prompt = SYSTEM_PROMPT + personality_section + profile_section + user_name_section + knowledge_context + master_prompt_section + rag_context
    
    contents.append({"role": "model", "parts": [{"text": "Understood. I will act immediately using tools without unnecessary chatter."}]})
    
    for msg in history:
        contents.append({
            "role": msg["role"] if msg["role"] == "model" else "user",
            "parts": [{"text": msg["text"]}]
        })
        
    # Append current message (with Image if present)
    import base64
    current_parts = [{"text": full_system_prompt}] # Wait, system prompt is prepended... messy strategy.
    
    # Better strategy: 
    # 1. System Prompt (as fake user message 1)
    # 2. History
    # 3. Current Message (User Text + Image)
    
    # We are rebuilding contents logic here
    contents = []
    
    # System Instruction (Implicitly handled by putting it in first user message or separate system_instruction field)
    # We will prepend it to the *current* message to ensure it's seen, OR rely on history structure.
    # The original code put it in first message.
    
    # Reconstruct history proper
    # First turn: System Prompt User -> Model "Understood"
    contents.append({"role": "user", "parts": [{"text": full_system_prompt}]})
    contents.append({"role": "model", "parts": [{"text": "Understood."}]})
    
    # History
    for msg in history[:-1]: # Exclude the just-added current message
         contents.append({
            "role": msg["role"] if msg["role"] == "model" else "user",
            "parts": [{"text": msg["text"]}]
        })
        
    # Current Message
    current_parts = []
    if image_data and mime_type:
        b64_data = base64.b64encode(image_data).decode('utf-8')
        current_parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": b64_data
            }
        })
    current_parts.append({"text": user_message})
    
    contents.append({"role": "user", "parts": current_parts})
    
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
                    print(f"[DEBUG] Model Response Parts: {parts}", file=sys.stderr)
                    
                    # 1. Check for functionCall (Prioritize over text for loop)
                    function_call_part = next((p for p in parts if 'functionCall' in p), None)
                    if function_call_part:
                        func_call = function_call_part['functionCall']
                        tool_name = func_call.get('name')
                        tool_args = func_call.get('args', {})
                        
                        print(f"[DEBUG] Executing tool: {tool_name}", file=sys.stderr)
                        tool_result = execute_tool(tool_name, tool_args, user_id=user_id)
                        
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
                            # Save model response to vector store for RAG
                            try:
                                from utils.vector_store import save_conversation
                                save_conversation(user_id, "model", response_text)
                            except:
                                pass
                            return response_text
            
            return '考えがまとまりませんでした...もう一度聞いてください。'
    
    except Exception as e:
        print(f"Gemini error: {e}", file=sys.stderr)
        return "ちょっとエラーが出ちゃいました...😢"
