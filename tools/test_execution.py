"""
Test script for verifying file creation in Google Drive
"""
import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env variables
load_dotenv()

from tools.google_ops import create_google_doc

def test_create_doc():
    print("Testing create_google_doc...")
    print(f"Target Shared Folder ID: {os.environ.get('GOOGLE_DRIVE_FOLDER_ID')}")
    
    result = create_google_doc("テストドキュメント_FromLocal", "これはローカル環境からのテスト作成です。共有ドライブに入っていれば成功です！")
    
    if result.get("error"):
        print(f"❌ Failed: {result['error']}")
    else:
        print(f"✅ Success!")
        print(f"   Title: {result.get('title')}")
        print(f"   URL: {result.get('url')}")
        if result.get("note"):
            print(f"   Note: {result.get('note')}")

if __name__ == "__main__":
    test_create_doc()
