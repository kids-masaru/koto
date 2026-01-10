from utils.storage import add_message, backup_history_to_drive
import sys

print("Testing Synchronous Backup...")
# Dummy data
add_message("test_sync_user", "user", "Synchronous backup test message")

# Run directly
backup_history_to_drive()

print("Backup function finished.")
