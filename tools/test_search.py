import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.web_ops import google_web_search

def test_search():
    query = "福岡 天気"
    print(f"Testing search for: {query}...")
    result = google_web_search(query)
    print(result)

if __name__ == "__main__":
    test_search()
