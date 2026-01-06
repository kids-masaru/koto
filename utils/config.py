import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'koto_config.json')

DEFAULT_CONFIG = {
    "user_name": "井崎さん",
    "personality": "元気な秘書",
    "knowledge_sources": [],  # List of {id, name, instruction}
    "reminder_time": "07:00",
    "reminder_prompt": "今日の天気、今日・明日・今週の予定とタスクを確認して、まとめて教えて！最後に今日も頑張ろうという気持ちになる一言をお願い！"
}

def load_config():
    """Load configuration from JSON file"""
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG

def save_config(config):
    """Save configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
