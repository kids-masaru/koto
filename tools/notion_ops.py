"""
Notion API integration for KOTO
Provides tools to read and write to Notion databases
"""
import os
import json
import urllib.request
import sys

NOTION_API_KEY = os.environ.get('NOTION_API_KEY', '')
NOTION_API_VERSION = "2022-06-28"

def _notion_request(endpoint, method="GET", data=None):
    """Make a request to Notion API"""
    if not NOTION_API_KEY:
        return {"error": "NOTION_API_KEY not set"}
    
    url = f"https://api.notion.com/v1/{endpoint}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json"
    }
    
    try:
        if data:
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method=method)
        else:
            req = urllib.request.Request(url, headers=headers, method=method)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Notion API Error: {e.code} - {error_body}", file=sys.stderr)
        return {"error": f"API Error: {e.code}", "details": error_body}
    except Exception as e:
        print(f"Notion request error: {e}", file=sys.stderr)
        return {"error": str(e)}


def list_notion_tasks(database_id, filter_today=False):
    """
    List tasks from a Notion database
    
    Args:
        database_id: The Notion database ID
        filter_today: If True, only return tasks due today
    
    Returns:
        List of tasks with title, status, due date
    """
    if not database_id:
        return {"error": "database_id is required"}
    
    # Build filter for today's tasks if requested
    body = {}
    if filter_today:
        from datetime import datetime, timezone, timedelta
        jst = timezone(timedelta(hours=9))
        today = datetime.now(jst).strftime("%Y-%m-%d")
        body["filter"] = {
            "property": "日付",  # Common Japanese property name for date
            "date": {
                "equals": today
            }
        }
    
    # Query the database
    result = _notion_request(f"databases/{database_id}/query", method="POST", data=body)
    
    if "error" in result:
        return result
    
    tasks = []
    for page in result.get("results", []):
        properties = page.get("properties", {})
        
        # Extract title (try common property names)
        title = ""
        for prop_name in ["名前", "タイトル", "Name", "Title", "タスク", "Task"]:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop.get("type") == "title" and prop.get("title"):
                    title = prop["title"][0].get("plain_text", "") if prop["title"] else ""
                    break
        
        # Extract status
        status = ""
        for prop_name in ["ステータス", "Status", "状態"]:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop.get("type") == "select" and prop.get("select"):
                    status = prop["select"].get("name", "")
                elif prop.get("type") == "status" and prop.get("status"):
                    status = prop["status"].get("name", "")
                break
        
        # Extract due date
        due_date = ""
        for prop_name in ["日付", "期限", "Due", "Date", "Due Date"]:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop.get("type") == "date" and prop.get("date"):
                    due_date = prop["date"].get("start", "")
                break
        
        if title:  # Only add if we found a title
            tasks.append({
                "id": page.get("id"),
                "title": title,
                "status": status,
                "due_date": due_date,
                "url": page.get("url", "")
            })
    
    return {"tasks": tasks, "count": len(tasks)}


def create_notion_task(database_id, title, due_date=None, status=None):
    """
    Create a new task in a Notion database
    
    Args:
        database_id: The Notion database ID
        title: Task title
        due_date: Optional due date (YYYY-MM-DD format)
        status: Optional status name
    
    Returns:
        Created task info
    """
    if not database_id:
        return {"error": "database_id is required"}
    if not title:
        return {"error": "title is required"}
    
    # Build the page properties
    properties = {
        "名前": {  # Try Japanese property name first
            "title": [
                {
                    "text": {
                        "content": title
                    }
                }
            ]
        }
    }
    
    # Add due date if provided
    if due_date:
        properties["日付"] = {
            "date": {
                "start": due_date
            }
        }
    
    # Add status if provided
    if status:
        properties["ステータス"] = {
            "select": {
                "name": status
            }
        }
    
    body = {
        "parent": {"database_id": database_id},
        "properties": properties
    }
    
    result = _notion_request("pages", method="POST", data=body)
    
    if "error" in result:
        return result
    
    return {
        "success": True,
        "id": result.get("id"),
        "url": result.get("url"),
        "title": title
    }


def update_notion_task(page_id, status=None, title=None):
    """
    Update an existing Notion task
    
    Args:
        page_id: The Notion page ID
        status: New status name
        title: New title
    
    Returns:
        Updated task info
    """
    if not page_id:
        return {"error": "page_id is required"}
    
    properties = {}
    
    if title:
        properties["名前"] = {
            "title": [
                {
                    "text": {
                        "content": title
                    }
                }
            ]
        }
    
    if status:
        properties["ステータス"] = {
            "select": {
                "name": status
            }
        }
    
    if not properties:
        return {"error": "No updates provided"}
    
    body = {"properties": properties}
    
    result = _notion_request(f"pages/{page_id}", method="PATCH", data=body)
    
    if "error" in result:
        return result
    
    return {
        "success": True,
        "id": result.get("id"),
        "url": result.get("url")
    }
