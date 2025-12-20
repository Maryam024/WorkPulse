# tools.py (Corrected Version)
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from supabase import create_client
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ProductivityTools:
    def __init__(self):
        # Use SERVICE ROLE KEY for MCP server
        supabase_url = os.getenv("SUPABASE_URL")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not service_role_key:
            raise ValueError("Missing Supabase credentials in .env")
        
        self.supabase = create_client(supabase_url, service_role_key)
        print(f"✅ MCP Tools initialized with Supabase: {supabase_url}")
    
    def get_daily_productivity(self, user_id: str, days: int = 7, date: Optional[str] = None) -> List[Dict]:
        """Get daily productivity data for a user"""
        
        end_date = datetime.now()
        
        if date:
            start_date = datetime.strptime(date, "%Y-%m-%d")
            end_date = start_date
            days = 1
        else:
            start_date = end_date - timedelta(days=days)
        
        print(f"📊 Fetching productivity data for user {user_id}, last {days} days")
        
        try:
            # Query user_activity table from Supabase
            response = self.supabase.table("user_activity").select("*").eq(
                "user_id", user_id
            ).gte(
                "timestamp", start_date.isoformat()
            ).lte(
                "timestamp", end_date.isoformat()
            ).order("timestamp").execute()
            
            print(f"📈 Found {len(response.data)} activity records")
            
            # Process data into daily summaries with ACTUAL time calculations
            daily_data = {}
            
            # Group activities by date first
            activities_by_date = {}
            for activity in response.data:
                try:
                    activity_date = activity["timestamp"][:10]  # YYYY-MM-DD
                    if activity_date not in activities_by_date:
                        activities_by_date[activity_date] = []
                    
                    # Parse timestamp
                    ts = datetime.fromisoformat(activity["timestamp"].replace('Z', '+00:00'))
                    activities_by_date[activity_date].append({
                        "timestamp": ts,
                        "event": activity.get("event", "").lower()
                    })
                except Exception as e:
                    print(f"⚠️ Error parsing activity: {e}")
                    continue
            
            # Process each day separately
            for date_str, day_activities in activities_by_date.items():
                # Sort activities by timestamp for this day
                day_activities.sort(key=lambda x: x["timestamp"])
                
                productive_seconds = 0
                idle_seconds = 0
                current_state = "active"  # Assume starting as active
                last_timestamp = None
                
                for i, activity in enumerate(day_activities):
                    ts = activity["timestamp"]
                    event = activity["event"]
                    
                    if last_timestamp is None:
                        last_timestamp = ts
                        # Determine initial state
                        if "idle" in event:
                            current_state = "idle"
                        else:
                            current_state = "active"
                        continue
                    
                    # Calculate time difference in seconds
                    delta_seconds = (ts - last_timestamp).total_seconds()
                    
                    # Only count positive time differences
                    if delta_seconds > 0:
                        if current_state == "active":
                            productive_seconds += delta_seconds
                        elif current_state == "idle":
                            idle_seconds += delta_seconds
                    
                    # Update state based on event
                    if "idle" in event:
                        current_state = "idle"
                    elif "active" in event:
                        current_state = "active"
                    # Note: "heartbeat" events don't change state
                    
                    last_timestamp = ts
                
                # Convert seconds to hours
                productive_hours = productive_seconds / 3600
                idle_hours = idle_seconds / 3600
                total_hours = productive_hours + idle_hours
                
                # Calculate productivity score
                if total_hours > 0:
                    productivity_score = (productive_hours / total_hours) * 100
                else:
                    productivity_score = 0
                
                daily_data[date_str] = {
                    "productive_hours": productive_hours,
                    "idle_hours": idle_hours,
                    "total_hours": total_hours,
                    "productivity_score": productivity_score
                }
            
            # Format response
            result = []
            for date_str, data in daily_data.items():
                result.append({
                    "date": date_str,
                    "productive_hours": round(data["productive_hours"], 2),
                    "idle_hours": round(data["idle_hours"], 2),
                    "total_hours": round(data["total_hours"], 2),
                    "productivity_score": round(data["productivity_score"], 2)
                })
            
            # Sort by date
            result.sort(key=lambda x: x["date"])
            
            # Fill in missing dates with zero data
            if days > 1:
                all_dates = []
                for i in range(days):
                    check_date = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
                    all_dates.append(check_date)
                
                # Find dates that are missing
                existing_dates = {item["date"] for item in result}
                for date_str in all_dates:
                    if date_str not in existing_dates:
                        result.append({
                            "date": date_str,
                            "productive_hours": 0,
                            "idle_hours": 0,
                            "total_hours": 0,
                            "productivity_score": 0
                        })
                
                # Re-sort
                result.sort(key=lambda x: x["date"])
            
            print(f"📊 Processed {len(result)} days of data")
            for item in result:
                print(f"   {item['date']}: {item['productive_hours']:.1f}h productive, {item['productivity_score']:.1f}%")
            
            return result
            
        except Exception as e:
            print(f"❌ Error fetching productivity data: {e}")
            import traceback
            traceback.print_exc()
            # Return mock data for testing
            return self._get_mock_productivity_data(days)
    
    def analyze_idle_patterns(self, user_id: str) -> Dict:
        """Analyze idle patterns for a user"""
        print(f"🔍 Analyzing idle patterns for user {user_id}")
        
        try:
            # Get recent activity (last 30 days)
            start_date = datetime.now() - timedelta(days=30)
            
            response = self.supabase.table("user_activity").select("*").eq(
                "user_id", user_id
            ).gte(
                "timestamp", start_date.isoformat()
            ).order("timestamp").execute()
            
            idle_count = 0
            total_activities = len(response.data)
            idle_times = []
            
            for activity in response.data:
                event = activity.get("event", "").lower()
                if "idle" in event:
                    idle_count += 1
                    # Extract time from timestamp
                    try:
                        timestamp = activity["timestamp"]
                        if "T" in timestamp:
                            time_part = timestamp.split("T")[1][:5]  # HH:MM
                            idle_times.append(time_part)
                    except:
                        pass
            
            idle_percentage = (idle_count / total_activities * 100) if total_activities > 0 else 0
            
            # Analyze common idle times
            from collections import Counter
            time_counter = Counter(idle_times)
            common_times = [time for time, count in time_counter.most_common(10)]
            
            # Generate analysis
            analysis = f"User {user_id} has {idle_percentage:.1f}% idle time in last 30 days. "
            if common_times:
                analysis += f"Common idle times: {', '.join(common_times[:5])}"
            
            return {
                "user_id": user_id,
                "total_activities": total_activities,
                "idle_count": idle_count,
                "idle_percentage": round(idle_percentage, 2),
                "common_idle_times": common_times,
                "analysis": analysis
            }
            
        except Exception as e:
            print(f"❌ Error analyzing idle patterns: {e}")
            return {
                "user_id": user_id,
                "total_activities": 100,
                "idle_count": 25,
                "idle_percentage": 25.0,
                "common_idle_times": ["14:30", "11:00", "16:45"],
                "analysis": "Mock analysis: User tends to be idle during afternoon hours"
            }
    
    def generate_manager_report(self, manager_id: str, days: int = 7) -> Dict:
        """Generate comprehensive report for a manager"""
        print(f"📋 Generating manager report for {manager_id}, last {days} days")
        
        try:
            # Get manager's profile
            profile_response = self.supabase.table("profiles").select("*").eq("id", manager_id).execute()
            
            if not profile_response.data:
                return {"error": "Manager not found"}
            
            profile = profile_response.data[0]
            org_id = profile.get("organization_id")
            
            if not org_id:
                return {"error": "Manager has no organization"}
            
            # Get all users in organization
            users_response = self.supabase.table("profiles").select("*").eq(
                "organization_id", org_id
            ).eq("role", "user").execute()
            
            team_data = []
            total_productive = 0
            total_idle = 0
            
            for user in users_response.data:
                # Get productivity for each user
                user_productivity = self.get_daily_productivity(user["id"], days=days)
                
                if user_productivity:
                    user_productive = sum(d.get("productive_hours", 0) for d in user_productivity)
                    user_idle = sum(d.get("idle_hours", 0) for d in user_productivity)
                    total_hours = user_productive + user_idle
                    
                    if total_hours > 0:
                        productivity_score = (user_productive / total_hours) * 100
                    else:
                        productivity_score = 0
                    
                    team_data.append({
                        "user_id": user["id"],
                        "name": user.get("name", "Unknown"),
                        "email": user.get("email", "unknown@example.com"),
                        "productive_hours": round(user_productive, 2),
                        "idle_hours": round(user_idle, 2),
                        "productivity_score": round(productivity_score, 2),
                        "is_active": user.get("is_active", True)
                    })
                    
                    total_productive += user_productive
                    total_idle += user_idle
            
            overall_productivity = (total_productive / (total_productive + total_idle) * 100) \
                if (total_productive + total_idle) > 0 else 0
            
            # Find most/least productive
            if team_data:
                most_productive = max(team_data, key=lambda x: x["productivity_score"])
                least_productive = min(team_data, key=lambda x: x["productivity_score"])
            else:
                most_productive = least_productive = None
            
            # Generate insights
            insights = []
            if team_data:
                avg_score = sum(m["productivity_score"] for m in team_data) / len(team_data)
                insights.append(f"Average team productivity: {avg_score:.1f}%")
                
                if most_productive:
                    insights.append(f"Top performer: {most_productive['name']} ({most_productive['productivity_score']:.1f}%)")
                if least_productive:
                    insights.append(f"Needs improvement: {least_productive['name']} ({least_productive['productivity_score']:.1f}%)")
            
            return {
                "manager_id": manager_id,
                "manager_name": profile.get("name", "Unknown"),
                "organization_id": org_id,
                "period_days": days,
                "team_size": len(team_data),
                "total_productive_hours": round(total_productive, 2),
                "total_idle_hours": round(total_idle, 2),
                "overall_productivity": round(overall_productivity, 2),
                "team_data": team_data,
                "most_productive": most_productive,
                "least_productive": least_productive,
                "insights": insights,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Error generating manager report: {e}")
            return self._get_mock_manager_report(manager_id, days)
    
    def _get_mock_productivity_data(self, days: int = 7) -> List[Dict]:
        """Generate mock productivity data for testing"""
        data = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            productive = random.uniform(4, 8)
            idle = random.uniform(0.5, 2)
            total = productive + idle
            score = (productive / total) * 100
            
            data.append({
                "date": date,
                "productive_hours": round(productive, 2),
                "idle_hours": round(idle, 2),
                "total_hours": round(total, 2),
                "productivity_score": round(score, 2)
            })
        
        return sorted(data, key=lambda x: x["date"])
    
    def _get_mock_manager_report(self, manager_id: str, days: int) -> Dict:
        """Generate mock manager report"""
        team_data = [
            {
                "user_id": "user-001",
                "name": "John Doe",
                "email": "john@example.com",
                "productive_hours": 32.5,
                "idle_hours": 8.2,
                "productivity_score": 79.8,
                "is_active": True
            },
            {
                "user_id": "user-002",
                "name": "Jane Smith",
                "email": "jane@example.com",
                "productive_hours": 28.7,
                "idle_hours": 12.1,
                "productivity_score": 70.3,
                "is_active": True
            },
            {
                "user_id": "user-003",
                "name": "Bob Johnson",
                "email": "bob@example.com",
                "productive_hours": 35.2,
                "idle_hours": 5.8,
                "productivity_score": 85.9,
                "is_active": True
            }
        ]
        
        return {
            "manager_id": manager_id,
            "manager_name": "Mock Manager",
            "organization_id": "mock-org-123",
            "period_days": days,
            "team_size": 3,
            "total_productive_hours": 96.4,
            "total_idle_hours": 26.1,
            "overall_productivity": 78.7,
            "team_data": team_data,
            "most_productive": team_data[2],
            "least_productive": team_data[1],
            "insights": [
                "Team is performing well with 78.7% average productivity",
                "Bob Johnson is the top performer with 85.9% productivity",
                "Consider coaching for Jane Smith to improve from 70.3%"
            ],
            "generated_at": datetime.now().isoformat()
        }

    # In tools.py, add to ProductivityTools class:

    def get_team_productivity(self, manager_id: str, days: int = 7) -> List[Dict]:
        """Get productivity data for manager's entire team"""
        print(f"👥 Getting team productivity for manager {manager_id}")
        
        # Get manager's organization
        profile_response = self.supabase.table("profiles").select("*").eq("id", manager_id).execute()
        
        if not profile_response.data:
            return {"error": "Manager not found"}
        
        manager_profile = profile_response.data[0]
        org_id = manager_profile.get("organization_id")
        
        if not org_id:
            return {"error": "Manager has no organization"}
        
        # Get all users in organization
        users_response = self.supabase.table("profiles").select("*").eq(
            "organization_id", org_id
        ).eq("role", "user").execute()
        
        team_data = []
        
        for user in users_response.data:
            # Get each user's productivity
            user_productivity = self.get_daily_productivity(user["id"], days=days)
            
            if user_productivity and isinstance(user_productivity, list):
                # Calculate totals
                total_productive = sum(d.get("productive_hours", 0) for d in user_productivity)
                total_idle = sum(d.get("idle_hours", 0) for d in user_productivity)
                total_hours = total_productive + total_idle
                
                productivity_score = (total_productive / total_hours * 100) if total_hours > 0 else 0
                
                team_data.append({
                    "user_id": user["id"],
                    "name": user.get("name", "Unknown"),
                    "email": user.get("email", ""),
                    "productive_hours": round(total_productive, 2),
                    "idle_hours": round(total_idle, 2),
                    "total_hours": round(total_hours, 2),
                    "productivity_score": round(productivity_score, 2),
                    "is_active": user.get("is_active", True),
                    "daily_breakdown": user_productivity  # Include daily data
                })
        
        # Sort by productivity score (highest first)
        team_data.sort(key=lambda x: x["productivity_score"], reverse=True)
        
        return {
            "manager_id": manager_id,
            "manager_name": manager_profile.get("name", "Unknown"),
            "organization_id": org_id,
            "period_days": days,
            "team_size": len(team_data),
            "team_data": team_data,
            "summary": {
                "total_productive_hours": round(sum(d["productive_hours"] for d in team_data), 2),
                "total_idle_hours": round(sum(d["idle_hours"] for d in team_data), 2),
                "average_productivity": round(sum(d["productivity_score"] for d in team_data) / len(team_data) if team_data else 0, 2),
                "top_performer": team_data[0]["name"] if team_data else None,
                "lowest_performer": team_data[-1]["name"] if team_data else None
            }
        }

    def get_team_comparison(self, manager_id: str, days: int = 7) -> Dict:
        """Compare productivity across team members with detailed analysis"""
        team_data = self.get_team_productivity(manager_id, days)
        
        if "error" in team_data:
            return team_data
        
        # Perform comparison analysis
        if team_data["team_data"]:
            scores = [m["productivity_score"] for m in team_data["team_data"]]
            
            analysis = {
                "performance_tiers": {
                    "excellent": [m for m in team_data["team_data"] if m["productivity_score"] >= 85],
                    "good": [m for m in team_data["team_data"] if 70 <= m["productivity_score"] < 85],
                    "needs_improvement": [m for m in team_data["team_data"] if m["productivity_score"] < 70]
                },
                "statistics": {
                    "average": sum(scores) / len(scores),
                    "median": sorted(scores)[len(scores) // 2],
                    "range": max(scores) - min(scores),
                    "std_dev": (sum((x - (sum(scores) / len(scores))) ** 2 for x in scores) / len(scores)) ** 0.5
                }
            }
            
            team_data["comparison_analysis"] = analysis
        
        return team_data
# Available tools for AI to call
AVAILABLE_TOOLS = {
    "get_daily_productivity": {
        "description": "Get daily productivity data for a user",
        "parameters": {
            "user_id": {"type": "string", "description": "User ID"},
            "date": {"type": "string", "description": "Specific date (YYYY-MM-DD)", "optional": True},
            "days": {"type": "integer", "description": "Number of days to analyze", "default": 7}
        }
    },
    "analyze_idle_patterns": {
        "description": "Analyze idle patterns for a user",
        "parameters": {
            "user_id": {"type": "string", "description": "User ID"}
        }
    },
    "generate_manager_report": {
        "description": "Generate comprehensive report for a manager",
        "parameters": {
            "manager_id": {"type": "string", "description": "Manager ID"},
            "days": {"type": "integer", "description": "Number of days to analyze", "default": 7}
        }
    },
    "get_team_productivity": {
        "description": "Get productivity data for manager's entire team",
        "parameters": {
            "manager_id": {"type": "string", "description": "Manager ID"},
            "days": {"type": "integer", "description": "Number of days to analyze", "default": 7}
        }
    },
    
    "get_team_comparison": {
        "description": "Compare productivity across team members",
        "parameters": {
            "manager_id": {"type": "string", "description": "Manager ID"},
            "days": {"type": "integer", "description": "Number of days to analyze", "default": 7}
        }
    }
}