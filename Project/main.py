# backend/main.py - CORRECTED VERSION

import os
import json
import time
import threading
import queue
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from pynput import mouse, keyboard

# Load env
load_dotenv("key.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Set SUPABASE_URL and SUPABASE_ANON_KEY in key.env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CONFIG_PATH = Path.home() / ".workpulse_config.json"

IDLE_THRESHOLD = 5  # 5 seconds of inactivity = idle
LOG_COOLDOWN = 3
MOUSE_UPDATE_INTERVAL = 0.5

# --- Global activity tracking state ---
last_activity_time = time.time()
last_input_type = "None"
is_idle = False
total_idle_time = 0.0
total_active_time = 0.0
last_state_change_time = time.time()
last_log_time = 0
last_mouse_log = 0

log_queue = queue.Queue()

# --- Worker to send logs to Supabase ---
def log_worker():
    while True:
        data = log_queue.get()
        if data is None:
            break
        try:
            supabase.table("user_activity").insert(data).execute()
            print(f"✅ Logged: {data['event']}")
        except Exception as e:
            print(f"⚠️ Logging error: {e}")
        log_queue.task_done()

threading.Thread(target=log_worker, daemon=True).start()

# --- Load or sign in user ---
def load_or_login():
    """Load local config or prompt user to login via Supabase Auth."""
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text())
        return cfg

    print("WorkPulse - Desktop agent first-time setup")
    email = input("Enter your WorkPulse email: ").strip()
    password = input("Enter your password: ").strip()

    try:
        resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if not resp.session:
            raise RuntimeError("Login failed. Check credentials.")

        cfg = {
            "user_id": resp.user.id,
            "access_token": resp.session.access_token,
            "refresh_token": resp.session.refresh_token,
            "signed_in_at": datetime.now(timezone.utc).isoformat()
        }
        CONFIG_PATH.write_text(json.dumps(cfg))
        print(f"✅ Signed in as {email} and saved local config.")
        return cfg

    except Exception as e:
        print("Login error:", e)
        raise

cfg = load_or_login()
USER_ID = cfg["user_id"]
print(f"Desktop agent USER_ID = {USER_ID}")

# --- Activity logging ---
def log_to_supabase(event, input_type=None):
    """Queue an activity log for Supabase."""
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "input_type": input_type,
        "user_id": USER_ID
    }
    log_queue.put(data)
    print(f"📝 Queueing: {event} ({input_type})")

def update_activity(input_type):
    """Update last activity timestamp and log if needed."""
    global last_activity_time, last_input_type, last_log_time
    last_activity_time = time.time()
    last_input_type = input_type
    
    # Only log "activity" events occasionally to avoid spam
    if time.time() - last_log_time > LOG_COOLDOWN:
        log_to_supabase("User activity", input_type)
        last_log_time = time.time()

# --- Mouse / Keyboard callbacks ---
def on_move(x, y):
    global last_mouse_log
    if time.time() - last_mouse_log > MOUSE_UPDATE_INTERVAL:
        update_activity("Mouse movement")
        last_mouse_log = time.time()

def on_click(x, y, button, pressed):
    if pressed:
        update_activity("Mouse click")

def on_scroll(x, y, dx, dy):
    update_activity("Mouse scroll")

def on_press(key):
    update_activity("Keyboard press")

def on_release(key):
    update_activity("Keyboard release")

# --- Fixed Idle monitoring ---
def monitor_idle():
    """Monitor user idle state and track time correctly."""
    global is_idle, last_state_change_time, last_activity_time
    global total_idle_time, total_active_time  # ADDED: Declare globals
    
    print("🚀 Idle monitor started...")
    
    while True:
        elapsed = time.time() - last_activity_time
        now = time.time()
        
        if elapsed > IDLE_THRESHOLD and not is_idle:
            # User JUST became idle
            # Active period = from last_state_change_time to (now - IDLE_THRESHOLD)
            idle_start_time = now - IDLE_THRESHOLD
            active_duration = idle_start_time - last_state_change_time
            
            if active_duration > 0:
                total_active_time += active_duration
            
            log_to_supabase("User became idle")
            print(f"🟡 User became idle (was active for {active_duration:.1f}s)")
            print(f"   Total active: {total_active_time:.1f}s, Total idle: {total_idle_time:.1f}s")
            
            is_idle = True
            last_state_change_time = idle_start_time
            
        elif elapsed <= IDLE_THRESHOLD and is_idle:
            # User JUST became active
            # Idle period = from last_state_change_time to now
            idle_duration = now - last_state_change_time
            
            if idle_duration > 0:
                total_idle_time += idle_duration
            
            log_to_supabase("User became active", last_input_type)
            print(f"🟢 User became active (was idle for {idle_duration:.1f}s)")
            print(f"   Total active: {total_active_time:.1f}s, Total idle: {total_idle_time:.1f}s")
            
            is_idle = False
            last_state_change_time = now
            
        time.sleep(1)  # Check every second

# --- Heartbeat logging ---
def heartbeat_worker():
    """Log regular heartbeat to track online status."""
    print("💓 Heartbeat monitor started...")
    while True:
        time.sleep(30)  # Every 30 seconds
        log_to_supabase("Heartbeat", "system")
        print(f"💓 Heartbeat sent - Active: {total_active_time:.1f}s, Idle: {total_idle_time:.1f}s")

# --- Session summary ---
def show_summary_and_save_session():
    """Save final session summary before exit."""
    global total_idle_time, total_active_time, is_idle, last_state_change_time
    
    now = time.time()
    
    # Add remaining time
    if is_idle:
        remaining_idle = now - last_state_change_time
        total_idle_time += remaining_idle
    else:
        remaining_active = now - last_state_change_time
        total_active_time += remaining_active
    
    active_minutes = total_active_time / 60
    idle_minutes = total_idle_time / 60
    
    print("\n" + "="*40)
    print("           SESSION SUMMARY")
    print("="*40)
    print(f"🟢 Active time: {active_minutes:.2f} minutes ({total_active_time:.1f}s)")
    print(f"🟡 Idle time:   {idle_minutes:.2f} minutes ({total_idle_time:.1f}s)")
    print("="*40)
    
    # Store session summary
    try:
        supabase.table("session_summary").insert({
            "user_id": USER_ID,
            "active_minutes": active_minutes,
            "idle_minutes": idle_minutes,
            "active_seconds": total_active_time,
            "idle_seconds": total_idle_time,
            "timestamp": datetime.utcnow().isoformat()
        }).execute()
        print("✅ Session summary saved to database")
    except Exception as e:
        print(f"❌ Failed to save session summary: {e}")

# --- Main ---
if __name__ == "__main__":
    print(f"\n{'='*50}")
    print("🚀 WorkPulse Desktop Agent Started")
    print(f"{'='*50}")
    print(f"📊 User ID: {USER_ID}")
    print(f"⏱️  Idle threshold: {IDLE_THRESHOLD} seconds")
    print(f"📝 Log cooldown: {LOG_COOLDOWN} seconds")
    print(f"{'='*50}\n")
    
    # Start listeners
    mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    
    mouse_listener.start()
    keyboard_listener.start()
    
    # Start monitoring threads
    threading.Thread(target=monitor_idle, daemon=True).start()
    threading.Thread(target=heartbeat_worker, daemon=True).start()
    
    print("✅ Monitoring started. Press Ctrl+C to exit.\n")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        show_summary_and_save_session()
        
        # Stop listeners
        mouse_listener.stop()
        keyboard_listener.stop()
        
        # Signal log worker to stop
        log_queue.put(None)
        log_queue.join()  # Wait for remaining logs
        
        print("✅ Graceful shutdown complete.")