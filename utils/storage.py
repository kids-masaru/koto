"""
Conversation history storage - JSON file based persistence
"""
import json
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Storage file path
DATA_DIR = Path(__file__).parent.parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"

# In-memory cache
_history_cache = None

# Maximum history per user
MAX_HISTORY = 50


def _ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(exist_ok=True)


def load_all_history():
    """Load all conversation history from file"""
    global _history_cache
    
    if _history_cache is not None:
        return _history_cache
    
    _ensure_data_dir()
    
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                _history_cache = defaultdict(list, json.load(f))
        except Exception as e:
            print(f"Error loading history: {e}")
            _history_cache = defaultdict(list)
    else:
        _history_cache = defaultdict(list)
    
    return _history_cache


def save_all_history():
    """Save all conversation history to file"""
    global _history_cache
    
    if _history_cache is None:
        return
    
    _ensure_data_dir()
    
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(dict(_history_cache), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")


def get_user_history(user_id):
    """Get conversation history for a specific user"""
    history = load_all_history()
    return history[user_id]


def add_message(user_id, role, text):
    """Add a message to user's conversation history"""
    history = load_all_history()
    
    history[user_id].append({
        "role": role,
        "text": text,
        "timestamp": datetime.now().isoformat()
    })
    
    # Trim to max history
    if len(history[user_id]) > MAX_HISTORY:
        history[user_id] = history[user_id][-MAX_HISTORY:]
    
    # Save after each message
    save_all_history()


def clear_user_history(user_id):
    """Clear conversation history for a specific user"""
    history = load_all_history()
    history[user_id] = []
    save_all_history()


def get_max_history():
    """Get the maximum history limit"""
    return MAX_HISTORY
