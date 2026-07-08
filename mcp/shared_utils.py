from datetime import datetime, timedelta, timezone

def calculate_productivity_stats(activity_data):
    """
    Calculate productive and idle hours from activity logs.
    Activity logs should contain:
    - "User became idle" events (start of idle period)
    - "User became active" events (end of idle period)
    - "Heartbeat" events (for online status)
    - "User activity" events (for active periods)
    """
    if not activity_data:
        return {
            "productive_hours": 0,
            "idle_hours": 0,
            "productive_minutes": 0,
            "idle_minutes": 0,
            "productivity_score": 0
        }
    
    # Sort by timestamp
    activity_data = sorted(activity_data, key=lambda x: x["timestamp"])
    
    total_idle_seconds = 0
    total_active_seconds = 0
    current_state = "active"  # Assume starting as active
    last_timestamp = None
    
    print(f"📊 Processing {len(activity_data)} activity records...")
    
    for i, entry in enumerate(activity_data):
        try:
            ts = datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))
            event = entry["event"]
            
            if last_timestamp is None:
                last_timestamp = ts
                # Determine initial state
                if event in ["User became idle", "Heartbeat"]:
                    current_state = "idle"
                else:
                    current_state = "active"
                continue
            
            # Calculate time difference in seconds
            delta_seconds = (ts - last_timestamp).total_seconds()
            
            if delta_seconds > 0:
                if current_state == "active":
                    total_active_seconds += delta_seconds
                else:
                    total_idle_seconds += delta_seconds
            
            # Update state based on event
            if event == "User became idle":
                current_state = "idle"
            elif event == "User became active":
                current_state = "active"
            
            last_timestamp = ts
            
        except Exception as e:
            print(f"⚠️ Error processing activity record {i}: {e}")
            continue
    
    # Convert seconds to hours AND minutes
    total_active_hours = total_active_seconds / 3600
    total_idle_hours = total_idle_seconds / 3600
    
    # Calculate minutes for dashboard
    productive_minutes = total_active_seconds / 60
    idle_minutes = total_idle_seconds / 60
    
    # Calculate productivity score
    work_hours = total_active_hours + total_idle_hours
    if work_hours > 0:
        productivity_score = (total_active_hours / work_hours) * 100
    else:
        productivity_score = 0
    
    return {
        "productive_hours": round(total_active_hours, 2),
        "idle_hours": round(total_idle_hours, 2),
        "productive_minutes": round(productive_minutes, 0),
        "idle_minutes": round(idle_minutes, 0),
        "productivity_score": round(productivity_score, 1)
    }