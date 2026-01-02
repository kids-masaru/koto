"""
Web operations - Google search and URL fetching
"""
import re
import urllib.request
import sys

try:
    from duckduckgo_search import DDGS
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    print("duckduckgo-search not available", file=sys.stderr)


def google_web_search(query, num_results=5):
    """
    Execute Web search and return top URLs
    Uses duckduckgo-search library (more reliable for free use)
    """
    try:
        if not SEARCH_AVAILABLE:
            return {"error": "検索機能が利用できません（duckduckgo-searchをインストールしてください）"}
        
        # Execute search
        urls = []
        with DDGS() as ddgs:
            # 1. Try default 'text' backend
            try:
                results = list(ddgs.text(query, max_results=num_results))
            except Exception:
                results = []
            
            # 2. Key Error or Empty? Try 'html' backend
            if not results:
                print("DDG 'text' backend failed/empty, trying 'html'...", file=sys.stderr)
                try:
                    results = list(ddgs.html(query, max_results=num_results))
                except Exception:
                    results = []

            # 3. Still empty? Try 'lite' backend
            if not results:
                print("DDG 'html' backend failed/empty, trying 'lite'...", file=sys.stderr)
                try:
                    results = list(ddgs.lite(query, max_results=num_results))
                except Exception:
                    results = []

            for r in results:
                # Normalizing keys (some backends use 'href', some might differ but DDGS standardizes usually)
                if 'href' in r:
                    urls.append(r['href'])
        
        if not urls:
            return {"success": True, "query": query, "urls": [], "message": "検索結果が見つかりませんでした"}
        
        return {
            "success": True,
            "query": query,
            "urls": urls,
            "count": len(urls)
        }
    except Exception as e:
        print(f"Search error: {e}", file=sys.stderr)
        return {"error": f"検索エラー: {str(e)}"}


def fetch_url(url):
    """
    Fetch content from URL and extract text
    Removes HTML tags for clean text output
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            content = res.read().decode('utf-8', errors='ignore')
            
            # Simple HTML to text (remove tags)
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
            content = re.sub(r'<[^>]+>', ' ', content)
            content = re.sub(r'\s+', ' ', content).strip()
            
            # Truncate if too long
            if len(content) > 5000:
                content = content[:5000] + "..."
            
            return {"success": True, "content": content, "url": url}
    except Exception as e:
        return {"error": f"URL取得エラー: {str(e)}"}
