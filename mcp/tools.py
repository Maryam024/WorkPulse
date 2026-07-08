# tools.py - USE REAL USER IDs
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

class ProductivityTools:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not service_role_key:
            raise ValueError("Missing Supabase credentials")
        
        self.supabase = create_client(supabase_url, service_role_key)
        print(f"✅ MCP Tools initialized with REAL database IDs")
    
    def get_daily_productivity(self, user_id: str, days: int = 7, date: Optional[str] = None) -> List[Dict]:
        """Get daily productivity data for a user - FIXED to return proper structure"""
        print(f"📊 Getting REAL productivity data for user ID: {user_id}, {days} days")
        
        try:
            end_date = datetime.now(timezone.utc)
            if date:
                start_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                days = 1
            else:
                start_date = end_date - timedelta(days=days)
            
            # Query activities
            response = self.supabase.table("user_activity").select("*").eq(
                "user_id", user_id
            ).gte("timestamp", start_date.isoformat()
            ).lte("timestamp", end_date.isoformat()
            ).order("timestamp").execute()
            
            print(f"📈 Found {len(response.data)} REAL activity records for user {user_id}")
            
            if not response.data:
                # Return empty but structured response
                result = []
                # Fill with empty data for each day
                for i in range(days):
                    date_str = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
                    result.append({
                        "date": date_str,
                        "productive_hours": 0,
                        "idle_hours": 0,
                        "productive_minutes": 0,
                        "idle_minutes": 0,
                        "productivity_score": 0,
                        "total_hours": 0
                    })
                
                # Sort by date (oldest to newest)
                result.sort(key=lambda x: x["date"])
                
                # Return structured result
                return {
                    "user_id": user_id,
                    "period_days": days,
                    "data": result,
                    "has_data": False,
                    "message": "No activity data found for this period"
                }
            
            # Group by date
            activities_by_date = {}
            for activity in response.data:
                date_str = activity["timestamp"][:10]  # YYYY-MM-DD
                if date_str not in activities_by_date:
                    activities_by_date[date_str] = []
                activities_by_date[date_str].append(activity)
            
            # Calculate productivity for each day
            result = []
            for date_str, daily_activities in activities_by_date.items():
                # Use the shared utility function
                from shared_utils import calculate_productivity_stats
                stats = calculate_productivity_stats(daily_activities)
                
                result.append({
                    "date": date_str,
                    "productive_hours": stats["productive_hours"],
                    "idle_hours": stats["idle_hours"],
                    "productive_minutes": stats["productive_minutes"],
                    "idle_minutes": stats["idle_minutes"],
                    "productivity_score": stats["productivity_score"],
                    "total_hours": stats["productive_hours"] + stats["idle_hours"]
                })
            
            # Sort by date
            result.sort(key=lambda x: x["date"])
            
            # If no data for some days, add zero entries
            if days > 1:
                all_dates = [(end_date - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
                existing_dates = {item["date"] for item in result}
                
                for date_str in all_dates:
                    if date_str not in existing_dates:
                        result.append({
                            "date": date_str,
                            "productive_hours": 0,
                            "idle_hours": 0,
                            "productive_minutes": 0,
                            "idle_minutes": 0,
                            "productivity_score": 0,
                            "total_hours": 0
                        })
                
                result.sort(key=lambda x: x["date"])
            
            return {
                "user_id": user_id,
                "period_days": days,
                "data": result,
                "has_data": True,
                "total_days": len(result),
                "average_productivity": sum(item["productivity_score"] for item in result) / len(result) if result else 0
            }
            
        except Exception as e:
            print(f"❌ Error getting REAL productivity data: {e}")
            return {
                "error": str(e),
                "user_id": user_id,
                "period_days": days,
                "data": [],
                "has_data": False,
                "message": f"Error retrieving data: {str(e)}"
            }
    
    def get_team_members(self, manager_id: str) -> List[Dict[str, Any]]:
        """Get team members for a manager"""
        print(f"👥 Getting team members for manager: {manager_id}")
        
        try:
            # Get users with this manager_id
            response = self.supabase.table("profiles").select(
                "id, name, email, role, is_active, manager_id"
            ).eq("manager_id", manager_id).execute()
            
            members = []
            for user in response.data:
                members.append({
                    "id": user["id"],  # UUID
                    "name": user.get("name", "Unknown"),
                    "email": user.get("email", ""),
                    "role": user.get("role", "user"),
                    "is_active": user.get("is_active", True),
                    "manager_id": manager_id
                })
            
            print(f"✅ Found {len(members)} team members")
            return members
            
        except Exception as e:
            print(f"❌ Error getting team members: {e}")
            return []
    
    def get_team_productivity(self, manager_id: str, days: int = 7) -> Dict[str, Any]:
        """Get team productivity"""
        print(f"📊 Getting team productivity for manager: {manager_id}")
        
        try:
            team_members = self.get_team_members(manager_id)
            
            if not team_members:
                return {
                    "success": True,
                    "has_data": False,
                    "team_data": [],
                    "summary": {
                        "team_size": 0,
                        "total_productive_hours": 0,
                        "total_idle_hours": 0,
                        "average_productivity": 0,
                        "active_members": 0
                    },
                    "period_days": days,
                    "manager_id": manager_id
                }
            
            team_data = []
            total_productive = 0
            total_idle = 0
            active_members = 0
            
            for member in team_members:
                # Get productivity for each member
                member_prod_response = self.get_daily_productivity(member["id"], days)
                
                # FIX: member_prod_response is a dict, not a list
                # Check if data exists and get the list from it
                member_data = member_prod_response.get("data", [])
                
                # Calculate member totals from the data list
                productive_hours = sum(d.get("productive_hours", 0) for d in member_data)
                idle_hours = sum(d.get("idle_hours", 0) for d in member_data)
                total_hours = productive_hours + idle_hours
                
                if total_hours > 0:
                    productivity_score = (productive_hours / total_hours) * 100
                else:
                    productivity_score = 0
                
                has_data = len(member_data) > 0 and productive_hours + idle_hours > 0
                if has_data:
                    active_members += 1
                
                team_data.append({
                    "user_id": member["id"],
                    "name": member["name"],
                    "email": member["email"],
                    "productive_hours": round(productive_hours, 2),
                    "idle_hours": round(idle_hours, 2),
                    "productive_minutes": round(productive_hours * 60, 0),
                    "idle_minutes": round(idle_hours * 60, 0),
                    "productivity_score": round(productivity_score, 2),
                    "total_hours": round(total_hours, 2),
                    "has_data": has_data
                })
                
                total_productive += productive_hours
                total_idle += idle_hours
            
            # Calculate team summary
            total_hours = total_productive + total_idle
            if total_hours > 0:
                avg_productivity = (total_productive / total_hours * 100)
            else:
                avg_productivity = 0
            
            # Sort by productivity score
            team_data.sort(key=lambda x: x["productivity_score"], reverse=True)
            
            return {
                "success": True,
                "has_data": active_members > 0,
                "team_data": team_data,
                "summary": {
                    "team_size": len(team_members),
                    "active_members": active_members,
                    "inactive_members": len(team_members) - active_members,
                    "total_productive_hours": round(total_productive, 2),
                    "total_idle_hours": round(total_idle, 2),
                    "total_productive_minutes": round(total_productive * 60, 0),
                    "total_idle_minutes": round(total_idle * 60, 0),
                    "total_work_hours": round(total_hours, 2),
                    "average_productivity": round(avg_productivity, 2)
                },
                "period_days": days,
                "manager_id": manager_id
            }
            
        except Exception as e:
            print(f"❌ Error getting team productivity: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "has_data": False,
                "team_data": [],
                "summary": {
                    "team_size": 0,
                    "total_productive_hours": 0,
                    "total_idle_hours": 0,
                    "average_productivity": 0
                }
            }
    def analyze_idle_patterns(self, user_id: str) -> Dict:
        """Analyze idle patterns for a user"""
        print(f"🔍 Analyzing idle patterns for user: {user_id}")
        
        try:
            # Get recent activity (last 30 days)
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            response = self.supabase.table("user_activity").select("*").eq(
                "user_id", user_id
            ).gte("timestamp", start_date.isoformat()
            ).order("timestamp").execute()
            
            idle_count = 0
            total_activities = len(response.data)
            idle_times = []
            
            for activity in response.data:
                event = activity.get("event", "").lower()
                if "idle" in event:
                    idle_count += 1
                    try:
                        timestamp = activity["timestamp"]
                        if "T" in timestamp:
                            time_part = timestamp.split("T")[1][:5]  # HH:MM
                            idle_times.append(time_part)
                    except:
                        pass
            
            idle_percentage = (idle_count / total_activities * 100) if total_activities > 0 else 0
            
            # Get common idle times
            from collections import Counter
            time_counter = Counter(idle_times)
            common_times = [time for time, count in time_counter.most_common(5)]
            
            return {
                "user_id": user_id,
                "total_activities": total_activities,
                "idle_count": idle_count,
                "idle_percentage": round(idle_percentage, 2),
                "common_idle_times": common_times,
                "has_data": total_activities > 0
            }
            
        except Exception as e:
            print(f"❌ Error analyzing idle patterns: {e}")
            return {
                "user_id": user_id,
                "total_activities": 0,
                "idle_count": 0,
                "idle_percentage": 0,
                "common_idle_times": [],
                "has_data": False
            }
    
    def get_team_idle_analysis(self, manager_id: str, days: int = 30) -> Dict[str, Any]:
        """Get team idle analysis"""
        print(f"🔍 Getting team idle analysis for manager: {manager_id}")
        
        try:
            team_members = self.get_team_members(manager_id)
            
            if not team_members:
                return {
                    "success": True,
                    "has_data": False,
                    "team_members": [],
                    "summary": {
                        "team_size": 0,
                        "average_idle_percentage": 0
                    }
                }
            
            team_data = []
            total_idle_pct = 0
            active_members = 0
            
            for member in team_members:
                member_idle = self.analyze_idle_patterns(member["id"])
                
                if member_idle["has_data"]:
                    team_data.append({
                        "user_id": member["id"],
                        "name": member["name"],
                        "idle_percentage": member_idle["idle_percentage"],
                        "total_activities": member_idle["total_activities"],
                        "idle_count": member_idle["idle_count"]
                    })
                    
                    total_idle_pct += member_idle["idle_percentage"]
                    active_members += 1
            
            avg_idle = total_idle_pct / active_members if active_members > 0 else 0
            
            return {
                "success": True,
                "has_data": active_members > 0,
                "team_members": team_data,
                "summary": {
                    "team_size": len(team_members),
                    "active_members": active_members,
                    "average_idle_percentage": round(avg_idle, 2)
                },
                "period_days": days,
                "manager_id": manager_id
            }
            
        except Exception as e:
            print(f"❌ Error getting team idle analysis: {e}")
            return {
                "success": False,
                "has_data": False,
                "team_members": [],
                "summary": {
                    "team_size": 0,
                    "average_idle_percentage": 0
                }
            }
    
    def generate_manager_report(self, manager_id: str, days: int = 7) -> Dict[str, Any]:
        """Generate manager report"""
        print(f"📋 Generating report for manager: {manager_id}")
        
        try:
            # Get team productivity data
            team_data = self.get_team_productivity(manager_id, days)
            
            if not team_data.get("has_data", False):
                return {
                    "success": True,
                    "has_data": False,
                    "manager_id": manager_id,
                    "period_days": days,
                    "team_size": 0,
                    "team_data": [],
                    "insights": ["No team data available"]
                }
            
            # Generate insights
            insights = []
            summary = team_data["summary"]
            
            if summary["team_size"] > 0:
                insights.append(f"Team size: {summary['team_size']} members")
                insights.append(f"Overall productivity: {summary['average_productivity']:.1f}%")
                insights.append(f"Active members: {summary['active_members']}")
                
                if team_data["team_data"]:
                    top = team_data["team_data"][0]
                    insights.append(f"Top performer: {top['name']} ({top['productivity_score']:.1f}%)")
            
            return {
                "success": True,
                "has_data": True,
                "manager_id": manager_id,
                "period_days": days,
                "team_size": summary["team_size"],
                "team_data": team_data["team_data"],
                "summary": summary,
                "insights": insights
            }
            
        except Exception as e:
            print(f"❌ Error generating report: {e}")
            return {
                "success": False,
                "has_data": False,
                "manager_id": manager_id,
                "period_days": days,
                "team_size": 0,
                "team_data": [],
                "insights": ["Error generating report"]
            }

AVAILABLE_TOOLS = {
    "get_daily_productivity": {
        "description": "Get daily productivity data for a user",
        "parameters": {
            "user_id": {"type": "string", "description": "User UUID"},
            "days": {"type": "integer", "description": "Number of days", "default": 7}
        }
    },
    "analyze_idle_patterns": {
        "description": "Analyze idle patterns for a user",
        "parameters": {
            "user_id": {"type": "string", "description": "User UUID"}
        }
    },
    "generate_manager_report": {
        "description": "Generate comprehensive report for a manager",
        "parameters": {
            "manager_id": {"type": "string", "description": "Manager UUID"},
            "days": {"type": "integer", "description": "Number of days", "default": 7}
        }
    },
    "get_team_productivity": {
        "description": "Get productivity data for all users under a manager",
        "parameters": {
            "manager_id": {"type": "string", "description": "Manager UUID"},
            "days": {"type": "integer", "description": "Number of days", "default": 7}
        }
    },
    "get_team_idle_analysis": {
        "description": "Get idle analysis for all users under a manager",
        "parameters": {
            "manager_id": {"type": "string", "description": "Manager UUID"},
            "days": {"type": "integer", "description": "Number of days", "default": 30}
        }
    }
}