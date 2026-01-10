"""
Profiler Agent (The Biographer)
Analyzes conversation history to build and update the user's psychological profile.
"""
import os
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional
import google.generativeai as genai
# Note: The user log says "support ended", suggesting a very new version or warning.
# However, for now we stick to what works in `agent.py` or just suppress warning.
# Actually, the error `Expecting value` was main crash. 
# We'll just keep `google.generativeai` but with better error handling as applied.
# Wait, I should synchronize with agent.py if possible. 
# agent.py imports: `from core.agent import get_gemini_response` (in app.py)
# agent.py uses `genai` from `google.generativeai`.
# So let's double check if I need to change import. 
# The log warning says "Please switch to `google.genai` package".
# For now, I'll ignore the warning and rely on logic fix. 
from utils.vector_store import _get_index, GeminiEmbedder

# Configure Gemini
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

PROFILE_FILE = "user_profile_data.json"

class ProfilerAgent:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp') # Use a smart model for analysis
        
    def run_analysis(self, user_id: str, days_back: int = 1) -> Dict:
        """Analyze recent conversations and update profile"""
        print(f"Profiler: Starting analysis for {user_id}...", file=sys.stderr)
        
        # 1. Fetch recent conversations from Pinecone
        recent_logs = self._fetch_recent_logs(user_id, days_back)
        if not recent_logs:
            print("Profiler: No new logs to analyze.", file=sys.stderr)
            return self._load_current_profile(user_id)

        # 2. Load existing profile
        current_profile = self._load_current_profile(user_id)
        
        # 3. Generate analysis prompting
        updated_profile = self._analyze_and_merge(current_profile, recent_logs)
        
        # 4. Save updated profile
        self._save_profile(user_id, updated_profile)
        
        print("Profiler: Profile updated successfully.", file=sys.stderr)
        return updated_profile

    def _fetch_recent_logs(self, user_id: str, days: int) -> List[str]:
        """Fetch logs from vector store (mock implementation for creating the logic first)"""
        # Note: Vector stores are optimized for semantic search, not time-based range queries usually.
        # Ideally, we should fetch by metadata filter. 
        # For Pinecone, we can filter by timestamp if stored as metadata number (not string).
        # Since we stored timestamp as string ISO, range query is hard.
        # Strategy: Fetch last N items or use a separate "recent_logs" buffer in Redis/File.
        
        # FOR NOW: Let's assume we fetch relevant memory summaries via vector search 
        # on generic "personality" keywords to see what's new.
        # OR better: The "Profiler" should ideally have access to raw logs.
        # Since we are using Pinecone only, let's query for "私のこと" (About me) related topics.
        
        index = _get_index()
        if not index: return []
        
        embedder = GeminiEmbedder()
        # Use a safe query text. If empty, Pinecone errors.
        query_text = "私について 好き 嫌い 考え 価値観"
        vector = embedder.embed_text(query_text)
        
        # Check if vector is valid (non-zero) - though embed_text usually handles this.
        # But if embedder fails, it might return None or list of zeros?
        if not vector or all(v == 0 for v in vector):
            print("Profiler Warning: Generated zero vector for query.", file=sys.stderr)
            return []
        
        results = index.query(
            vector=vector,
            top_k=50, # Get plenty
            filter={"user_id": user_id},
            include_metadata=True
        )
        
        logs = []
        for match in results.matches:
             if match.metadata and match.metadata.get('role') == 'user':
                 text = match.metadata.get('text', '')
                 # TODO: Filter strictly by date here if possible in python
                 logs.append(text)
                 
        return logs

    def _analyze_and_merge(self, current_profile: Dict, logs: List[str]) -> Dict:
        """Ask Gemini to update the profile based on new logs"""
        
        logs_text = "\n".join([f"- {log}" for log in logs])
        current_profile_str = json.dumps(current_profile, ensure_ascii=False, indent=2)
        
        # Get prompt from config or use default
        from utils.sheets_config import load_config
        config = load_config()
        
        system_prompt = config.get('profiler_prompt', """
        あなたは「栞（しおり）」という名の、心優しい伝記作家です。
        対象人物（ユーザー）の会話記録（Log）を読み、現在の人物プロファイル（Profile）を更新してください。
        
        【指示】
        1. 新しい会話から読み取れる「性格」「興味関心」「価値観」「悩み」「目標」を抽出してください。
        2. 現在のプロファイルと矛盾する場合は、新しい情報を優先して書き換えてください。
        3. 以前の情報で、変わっていない部分は維持してください。
        4. 出力は必ず以下のJSON形式のみで行ってください。
        
        {{
            "name": "推定または既知の名前",
            "personality_traits": ["特徴1", "特徴2", ...],
            "interests": ["興味1", "興味2", ...],
            "values": ["価値観1", ...],
            "current_goals": ["目標1", ...],
            "summary": "人物像の簡潔な要約（200文字以内）"
        }}
        """)

        prompt = f"""
        {system_prompt}
        
        【現在のプロファイル】
        {current_profile_str}
        
        【新しい会話記録（断片）】
        {logs_text}
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            # Clean up markdown code blocks if present
            if "```json" in text:
                import re
                match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
                if match:
                    text = match.group(1)
            elif "```" in text:
                 text = text.replace("```", "")
            
            return json.loads(text)
        except Exception as e:
            print(f"Profiler Logic Error: {e}", file=sys.stderr)
            # Return current profile instead of crashing, so we don't wipe data
            return current_profile

    def _load_current_profile(self, user_id: str) -> Dict:
        """Load from persistent vector store"""
        from utils.vector_store import get_user_profile
        return get_user_profile(user_id)

    def _save_profile(self, user_id: str, profile: Dict):
        """Save to persistent vector store"""
        from utils.vector_store import save_user_profile
        save_user_profile(user_id, profile)

profiler = ProfilerAgent()
