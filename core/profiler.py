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
        vector = embedder.embed_text("私について 好き 嫌い 考え 価値観") # Query for self-disclosure
        
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
        
        prompt = f"""
        あなたは「伝記作家」です。
        対象人物（ユーザー）の会話記録（Log）を読み、現在の人物プロファイル（Profile）を更新してください。
        
        【現在のプロファイル】
        {current_profile_str}
        
        【新しい会話記録（断片）】
        {logs_text}
        
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
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            # Clean up markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:-3]
            return json.loads(text)
        except Exception as e:
            print(f"Profiler Logic Error: {e}", file=sys.stderr)
            return current_profile

    def _load_current_profile(self, user_id: str) -> Dict:
        """Load from local JSON file (simulated DB)"""
        try:
            with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(user_id, {})
        except FileNotFoundError:
            return {}

    def _save_profile(self, user_id: str, profile: Dict):
        """Save to local JSON file"""
        all_data = {}
        try:
            with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        except FileNotFoundError:
            pass
            
        all_data[user_id] = profile
        
        with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)

profiler = ProfilerAgent()
