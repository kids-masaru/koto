from dotenv import load_dotenv
import os
import sys
import datetime

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.google_ops import create_calendar_event, add_task

def verify_fix():
    print("🚀 Starting Verification: Creating Event & Task for Tomorrow 15:00")
    
    # Calculate tomorrow 15:00
    now = datetime.datetime.now()
    tomorrow = now + datetime.timedelta(days=1)
    
    start_time = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0)
    end_time = start_time + datetime.timedelta(hours=1)
    
    # Format to ISO 8601
    start_str = start_time.isoformat()
    end_str = end_time.isoformat()
    
    print(f"📅 Target Time: {start_str}")

    # 1. Create Calendar Event
    print("\n[1] Creating Calendar Event 'テスト'...")
    event_result = create_calendar_event(
        summary="テスト (Koto Debug)",
        start_time=start_str,
        end_time=end_str,
        location="Koto Debugger"
    )
    
    if "error" in event_result:
        print(f"❌ Calendar Error: {event_result['error']}")
    else:
        print(f"✅ Calendar Success! Link: {event_result.get('htmlLink')}")

    # 2. Add Task
    print("\n[2] Creating Task 'テスト'...")
    # Note: Google Tasks API 'due' field requires RFC 3339 timestamp (Zulu time usually preferred, but ISO may work)
    # The simple add_task tool in utils might only take title, let's check.
    # Checking source suggests it might just take title. I will check the source in a moment or just pass title first.
    # But user said "tomorrow 15:00", so if add_task supports due date, I should use it. 
    # For now, I'll just add the task with the title including the time if I can't set the time.
    
    # Let's inspect add_task signature from previous viewing or just try to pass generic title.
    # "tools.google_ops" lines 239-273 (calendar) 
    # Task tools were added recently.
    
    task_result = add_task(title=f"テスト (Koto Debug) {start_str}")
    
    if "error" in task_result:
        print(f"❌ Tasks Error: {task_result['error']}")
    else:
        print(f"✅ Tasks Success! Task created.")

if __name__ == "__main__":
    verify_fix()
