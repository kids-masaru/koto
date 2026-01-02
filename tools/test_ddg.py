from duckduckgo_search import DDGS

def test_ddg():
    print("Testing DuckDuckGo Search...")
    with DDGS() as ddgs:
        results = list(ddgs.text("福岡 天気", max_results=5))
        for r in results:
            print(f"- {r['title']}: {r['href']}")

if __name__ == "__main__":
    test_ddg()
