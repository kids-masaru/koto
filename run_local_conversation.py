"""
Local interactive chat with Koto (Gemini Agent)
Simulates the LINE bot behavior in the terminal.
"""
import sys
import os
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load env
load_dotenv()

from core.agent import get_gemini_response

def main():
    print("=== Koto Local Debug Client ===")
    print("Type 'exit' to quit.")
    
    user_id = "local_debug_user"
    
    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            
            if not user_input.strip():
                continue
                
            print("Koto thinking...", end="", flush=True)
            
            # get_gemini_response is synchronous in the current code based on previous file reads
            # If it were async, we'd need loop.run_until_complete, but core/agent.py seemed sync (requests/google-api).
            # Let's check agent.py again if needed, but for now assume sync as per previous `utils/auth` etc.
            response = get_gemini_response(user_id, user_input)
            
            print(f"\rKoto: {response}")
            
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
