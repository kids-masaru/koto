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


def google_web_search(query, num_results=3):
    """
    Execute Web search and return top URLs
    Uses duckduckgo-search library (more reliable for free use)
    """
    try:
        if not SEARCH_AVAILABLE:
            return {"error": "検索機能が利用できません（duckduckgo-searchをインストールしてください）"}
        
        # Execute search
        search_results = []
        # Set timeout to avoid Reply Token expiration (Line limits 30s)
        with DDGS(timeout=5) as ddgs:
            # 1. Try default 'text' backend with JP region
            try:
                results = list(ddgs.text(query, region='jp-jp', max_results=num_results))
            except Exception:
                results = []
            
            # 2. Backups (html/lite)
            if not results:
                try:
                    results = list(ddgs.html(query, region='jp-jp', max_results=num_results))
                except Exception:
                    results = []
            
            if not results:
                try:
                    results = list(ddgs.lite(query, region='jp-jp', max_results=num_results))
                except Exception as e:
                    print(f"DDG Search Error (lite): {e}", file=sys.stderr)
                    results = []

            for r in results:
                search_results.append({
                    "title": r.get('title', 'No Title'),
                    "url": r.get('href', ''),
                    "snippet": r.get('body', '') or r.get('snippet', '')
                })
        
        # Fallback: If no results found (likely IP blocked), return a direct search URL
        if not search_results:
            print("Search returned 0 results. Using fallback URL.", file=sys.stderr)
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            search_results.append({
                "title": f"Google検索: {query}",
                "url": search_url,
                "snippet": "検索結果をうまく読み取れませんでした。リンク先で直接確認してください。"
            })
        
        return {
            "success": True,
            "query": query,
            "results": search_results,
            "count": len(search_results)
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
