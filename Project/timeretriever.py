from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime
import os

# Load env variables
load_dotenv("key.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Fetch events from Supabase
response = supabase.table("user_activity").select("*").order("timestamp", desc=False).execute()
data = response.data

if not data:
    print("No activity data found.")
    exit()

# Track time spent in each state
total_idle = 0
total_active = 0
last_event_time = None
last_state = None

for entry in data:
    ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
    event = entry["event"]

    if last_event_time is not None:
        delta = (ts - last_event_time).total_seconds()
        if last_state == "User became idle":
            total_idle += delta
        elif last_state in ("User activity", "User became active"):
            total_active += delta

    last_event_time = ts
    last_state = event

# Print summary
print("\n========== ACTIVITY SUMMARY ==========")
print(f"🟢 Active time: {total_active / 60:.2f} minutes")
print(f"🟡 Idle time:   {total_idle / 60:.2f} minutes")
print("=====================================")
