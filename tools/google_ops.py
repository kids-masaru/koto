"""
Google Workspace operations - Docs, Sheets, Slides, Drive, Gmail
"""
import sys
from googleapiclient.discovery import build
from utils.auth import get_google_credentials, get_shared_folder_id


def move_to_shared_folder(file_id):
    """
    Move a file to the shared folder specified in GOOGLE_DRIVE_FOLDER_ID
    This makes files created by Service Account visible to users
    """
    folder_id = get_shared_folder_id()
    if not folder_id:
        print("Warning: GOOGLE_DRIVE_FOLDER_ID not set. File will be in Service Account's root.", file=sys.stderr)
        return {"success": True, "note": "Shared folder not configured"}
    
    try:
        creds = get_google_credentials()
        if not creds:
            return {"success": False, "error": "Credential error during move"}
        
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Get current parents (supportsAllDrives=True needed for Shared Drives)
        file = drive_service.files().get(
            fileId=file_id, 
            fields='parents',
            supportsAllDrives=True
        ).execute()
        previous_parents = ",".join(file.get('parents', []))
        
        # Move to shared folder
        drive_service.files().update(
            fileId=file_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields='id, parents',
            supportsAllDrives=True
        ).execute()
        
        print(f"Moved file {file_id} to shared folder {folder_id}", file=sys.stderr)
        return {"success": True}
    except Exception as e:
        print(f"Error moving to shared folder: {e}", file=sys.stderr)
        return {"success": False, "error": str(e)}


def create_google_doc(title, content=""):
    """Create a Google Doc directly in the shared folder"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "Google認証に失敗しました。環境変数を確認してください。"}
        
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        
        folder_id = get_shared_folder_id()
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.document'
        }
        
        # If shared folder is set, create directly inside it
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        # 1. Create file using Drive API
        file = drive_service.files().create(
            body=file_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()
        doc_id = file.get('id')
        
        # 2. Insert content using Docs API
        if content:
            requests = [{'insertText': {'location': {'index': 1}, 'text': content}}]
            docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
        
        url = f"https://docs.google.com/document/d/{doc_id}/edit"
        return {"success": True, "title": title, "url": url, "id": doc_id}
    except Exception as e:
        print(f"Docs error: {e}", file=sys.stderr)
        return {"error": f"ドキュメント作成中にエラーが発生しました: {str(e)}"}


def create_google_sheet(title, data=None):
    """Create a Google Sheet directly in the shared folder"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "Google認証に失敗しました。環境変数を確認してください。"}
        
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        folder_id = get_shared_folder_id()
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
            
        # 1. Create using Drive API
        file = drive_service.files().create(
            body=file_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()
        sheet_id = file.get('id')
        
        # 2. Update content using Sheets API
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
        return {"error": f"スプレッドシート作成中にエラーが発生しました: {str(e)}"}


def create_google_slide(title):
    """Create a Google Slides presentation directly in the shared folder"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "Google認証に失敗しました。環境変数を確認してください。"}
        
        drive_service = build('drive', 'v3', credentials=creds)
        
        folder_id = get_shared_folder_id()
        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.presentation'
        }
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
            
        file = drive_service.files().create(
            body=file_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()
        pres_id = file.get('id')
        
        url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
        return {"success": True, "title": title, "url": url, "id": pres_id}
    except Exception as e:
        return {"error": f"スライド作成中にエラーが発生しました: {str(e)}"}


def search_drive(query):
    """Search Google Drive for files"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "Google認証に失敗しました。"}
        
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Escape single quotes in query to prevent syntax errors
        safe_query = query.replace("'", "\\'")
        
        # Search includes Shared Drives
        results = drive_service.files().list(
            q=f"name contains '{safe_query}' and trashed=false",
            pageSize=10,
            fields="files(id, name, mimeType, webViewLink, modifiedTime)",
            corpora='allDrives',
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute()
        
        files = results.get('files', [])
        return {"success": True, "files": files, "count": len(files)}
    except Exception as e:
        return {"error": f"検索中にエラーが発生しました: {str(e)}"}


def list_gmail(query="is:unread", max_results=5):
    """List Gmail messages matching query"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "Google認証に失敗しました。"}

        gmail_service = build('gmail', 'v1', credentials=creds)

        results = gmail_service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()

        messages = results.get('messages', [])

        if not messages:
            return {"success": True, "emails": [], "count": 0}

        email_list = []
        for msg in messages[:max_results]:
            try:
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
                    'date': headers.get('Date', ''),
                    'snippet': msg_data.get('snippet', '')
                })
            except Exception as e:
                print(f"Error getting message: {e}", file=sys.stderr)
                continue

        return {"success": True, "emails": email_list, "count": len(email_list)}
    except Exception as e:
        print(f"Gmail error: {e}", file=sys.stderr)
        return {"error": f"Gmail操作中にエラーが発生しました: {str(e)}"}


def get_gmail_body(message_id: str):
    """Fetch full email body (plain text) for a given Gmail message ID."""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "Google認証に失敗しました。"}
        gmail_service = build('gmail', 'v1', credentials=creds)
        msg = gmail_service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        # Extract headers
        headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
        # Extract plain text body (may be nested parts)
        def get_plain_text(part):
            if part.get('mimeType') == 'text/plain' and 'data' in part.get('body', {}):
                import base64
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
            for sub in part.get('parts', []):
                txt = get_plain_text(sub)
                if txt:
                    return txt
            return ''
        body = get_plain_text(msg.get('payload', {}))
        return {
            "success": True,
            "id": message_id,
            "subject": headers.get('Subject', '(件名なし)'),
            "from": headers.get('From', ''),
            "date": headers.get('Date', ''),
            "body": body
        }
    except Exception as e:
        print(f"Gmail body error: {e}", file=sys.stderr)
        return {"error": f"メール本文取得中にエラーが発生しました: {str(e)}"}

    """List Gmail messages matching query"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "Google認証に失敗しました。"}
        
        gmail_service = build('gmail', 'v1', credentials=creds)
        
        results = gmail_service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            return {"success": True, "emails": [], "count": 0}
        
        email_list = []
        
        for msg in messages[:max_results]:
            try:
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
                    'date': headers.get('Date', ''),
                    'snippet': msg_data.get('snippet', '')
                })
            except Exception as e:
                print(f"Error getting message: {e}", file=sys.stderr)
                continue
        
        return {"success": True, "emails": email_list, "count": len(email_list)}
    except Exception as e:
        print(f"Gmail error: {e}", file=sys.stderr)
        return {"error": f"Gmail操作中にエラーが発生しました: {str(e)}"}
