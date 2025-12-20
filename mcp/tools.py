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
            
            # Process data into daily summaries
            daily_data = {}
            for activity in response.data:
                try:
                    activity_date = activity["timestamp"][:10]  # Get YYYY-MM-DD
                    
                    if activity_date not in daily_data:
                        daily_data[activity_date] = {
                            "productive_hours": 0,
                            "idle_hours": 0,
                            "total_hours": 0
                        }
                    
                    # Calculate based on event type (simplified logic)
                    event = activity.get("event", "").lower()
                    if "idle" in event:
                        daily_data[activity_date]["idle_hours"] += 0.1  # Simplified
                    elif "active" in event or "heartbeat" in event:
                        daily_data[activity_date]["productive_hours"] += 0.1
                    
                    daily_data[activity_date]["total_hours"] += 0.1
                    
                except Exception as e:
                    print(f"⚠️ Error processing activity: {e}")
                    continue
            
            # Format response
            result = []
            for date_str, data in daily_data.items():
                if data["total_hours"] > 0:
                    productivity_score = (data["productive_hours"] / data["total_hours"]) * 100
                else:
                    productivity_score = 0
                    
                result.append({
                    "date": date_str,
                    "productive_hours": round(data["productive_hours"], 2),
                    "idle_hours": round(data["idle_hours"], 2),
                    "total_hours": round(data["total_hours"], 2),
                    "productivity_score": round(productivity_score, 2)
                })
            
            # Sort by date
            result.sort(key=lambda x: x["date"])
            
            # If no real data, use mock data
            if not result:
                print("📊 No real data found, using mock data")
                result = self._get_mock_productivity_data(days)
            
            return result
            
        except Exception as e:
            print(f"❌ Error fetching productivity data: {e}")
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
    }
}