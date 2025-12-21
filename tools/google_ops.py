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
        return  # No shared folder configured, skip
    
    try:
        creds = get_google_credentials()
        if not creds:
            return
        
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Get current parents
        file = drive_service.files().get(fileId=file_id, fields='parents').execute()
        previous_parents = ",".join(file.get('parents', []))
        
        # Move to shared folder
        drive_service.files().update(
            fileId=file_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields='id, parents'
        ).execute()
        
        print(f"Moved file {file_id} to shared folder {folder_id}", file=sys.stderr)
    except Exception as e:
        print(f"Error moving to shared folder: {e}", file=sys.stderr)


def create_google_doc(title, content=""):
    """Create a Google Doc and move it to shared folder"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "認証エラー"}
        
        docs_service = build('docs', 'v1', credentials=creds)
        
        doc = docs_service.documents().create(body={'title': title}).execute()
        doc_id = doc.get('documentId')
        
        if content:
            requests = [{'insertText': {'location': {'index': 1}, 'text': content}}]
            docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
        
        # Move to shared folder
        move_to_shared_folder(doc_id)
        
        url = f"https://docs.google.com/document/d/{doc_id}/edit"
        return {"success": True, "title": title, "url": url, "id": doc_id}
    except Exception as e:
        print(f"Docs error: {e}", file=sys.stderr)
        return {"error": str(e)}


def create_google_sheet(title, data=None):
    """Create a Google Sheet and move it to shared folder"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "認証エラー"}
        
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        spreadsheet = {'properties': {'title': title}}
        result = sheets_service.spreadsheets().create(body=spreadsheet).execute()
        sheet_id = result.get('spreadsheetId')
        
        if data:
            sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='A1',
                valueInputOption='RAW',
                body={'values': data}
            ).execute()
        
        # Move to shared folder
        move_to_shared_folder(sheet_id)
        
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        return {"success": True, "title": title, "url": url, "id": sheet_id}
    except Exception as e:
        return {"error": str(e)}


def create_google_slide(title):
    """Create a Google Slides presentation and move it to shared folder"""
    try:
        creds = get_google_credentials()
        if not creds:
            return {"error": "認証エラー"}
        
        slides_service = build('slides', 'v1', credentials=creds)
        
        presentation = {'title': title}
        result = slides_service.presentations().create(body=presentation).execute()
        pres_id = result.get('presentationId')
        
        # Move to shared folder
        move_to_shared_folder(pres_id)
        
        url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
        return {"success": True, "title": title, "url": url, "id": pres_id}
    except Exception as e:
        return {"error": str(e)}


def search_drive(query):
    """Search Google Drive for files"""
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
        return {"error": str(e)}


def list_gmail(query="is:unread", max_results=5):
    """List Gmail messages matching query"""
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
                    'date': headers.get('Date', '')
                })
            except Exception as e:
                print(f"Error getting message: {e}", file=sys.stderr)
                continue
        
        return {"success": True, "emails": email_list, "count": len(email_list)}
    except Exception as e:
        print(f"Gmail error: {e}", file=sys.stderr)
        return {"error": f"Gmailエラー: {str(e)}"}
