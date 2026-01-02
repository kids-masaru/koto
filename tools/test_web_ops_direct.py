import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.web_ops import google_web_search

def test_ops():
    print("Testing google_web_search from tools...")
    result = google_web_search("福岡 天気")
    print(f"Result keys: {result.keys()}")
    if 'results' in result:
        for i, r in enumerate(result['results'][:2]):
            print(f"--- Result {i} ---")
            print(f"Title: {r.get('title')}")
            print(f"Snippet: {r.get('snippet')[:50]}...")
            print(f"URL: {r.get('url')}")
    else:
        print("No results found or error.")
        print(result)

if __name__ == "__main__":
    test_ops()
