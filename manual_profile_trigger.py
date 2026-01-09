from app import app, run_profiler

print("Starting manual profiler run...")
try:
    with app.app_context():
        run_profiler()
    print("Manual profiler run completed successfully.")
except Exception as e:
    print(f"Error during manual run: {e}")
