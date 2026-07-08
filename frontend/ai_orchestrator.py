# ai_orchestrator.py - MUST USE REAL USER IDs
from datetime import datetime
import os
import requests
from dotenv import load_dotenv
from clean_response import CleanResponseBuilder

load_dotenv()

class AIOrchestrator:
    """Orchestrates AI queries - MUST RECEIVE REAL USER IDs FROM APP"""
    
    def __init__(self):
        self.mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
        print(f"✅ AI Orchestrator initialized")
    
    def _classify_intent(self, query: str) -> dict:
        """Classify query intent"""
        query_lower = query.lower()
        
        # Greetings first
        if any(word in query_lower for word in ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"]):
            return {"intent": "greeting", "actionable": False}
        elif any(word in query_lower for word in ["team", "everyone", "members", "staff", "employees"]):
            return {"intent": "team_analysis", "actionable": True}
        elif "idle" in query_lower:
            return {"intent": "idle_analysis", "actionable": True}
        elif "report" in query_lower:
            return {"intent": "report_request", "actionable": True}
        elif any(word in query_lower for word in ["productivity", "today", "weekly", "daily", "trend"]):
            return {"intent": "productivity_query", "actionable": True}
        else:
            return {"intent": "general", "actionable": True}
    
    def _determine_tool(self, query: str, user_role: str) -> str:
        """Determine which tool to use"""
        query_lower = query.lower()
        
        if user_role == "manager":
            # Manager-specific queries
            if any(word in query_lower for word in ["team", "everyone", "members", "staff"]):
                if "idle" in query_lower:
                    return "get_team_idle_analysis"
                elif "report" in query_lower:
                    return "generate_manager_report"
                else:
                    return "get_team_productivity"
            
            # If manager asks about idle patterns WITHOUT specifying team
            # They probably mean team idle patterns
            elif "idle" in query_lower:
                return "get_team_idle_analysis"  # Changed from analyze_idle_patterns
            
            # Personal productivity queries
            elif any(word in query_lower for word in ["my", "me", "i", "personal", "myself"]):
                return "get_daily_productivity"
            
            # Default for manager is to show team data
            # (since managers usually care about team, not personal)
            return "get_team_productivity"
        
        # User queries
        else:
            if "idle" in query_lower:
                return "analyze_idle_patterns"
            else:
                return "get_daily_productivity"

    
    def _execute_tool(self, tool_name: str, parameters: dict) -> dict:
        """Execute tool via MCP server"""
        try:
            response = requests.post(
                f"{self.mcp_server_url}/execute_tool/{tool_name}",
                json=parameters,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _extract_parameters(self, tool_name: str, query: str, user_id: str) -> dict:
        """Extract parameters"""
        query_lower = query.lower()
        
        base_params = {"user_id": user_id}
        
        if tool_name == "get_daily_productivity":
            days = 1 if "today" in query_lower else 7 if "weekly" in query_lower else 1
            return {"user_id": user_id, "days": days}  # FIXED: days not daays
        
        elif tool_name == "get_team_productivity":
            days = 7
            return {"manager_id": user_id, "days": days}  # FIXED: days not 'days'
        
        elif tool_name == "get_team_idle_analysis":
            days = 30
            return {"manager_id": user_id, "days": days}  # FIXED: days not 'days'
        
        elif tool_name == "generate_manager_report":
            days = 7
            return {"manager_id": user_id, "days": days}
        
        elif tool_name == "analyze_idle_patterns":
            return {"user_id": user_id}
        
        return {"user_id": user_id}

    # Also update the process_query method to handle greeting properly:

    def process_query(self, user_id: str, query: str, user_role: str = None) -> dict:
        """Process query"""
        print(f"\n🔍 Processing query: '{query}' for user: {user_id[:8]}... (Role: {user_role})")

        if not user_id:
            return CleanResponseBuilder.build_error_response(
                query=query,
                user_id="unknown",
                user_role=user_role or "user",
                error_message="User not authenticated",
                tool_used="none",
                tool_parameters={}
            )
        
        # Classify intent
        intent = self._classify_intent(query)
        print(f"🎯 Detected intent: {intent['intent']}")
        
        # Handle greeting - FIXED to use proper greeting response
        if intent["intent"] == "greeting" or not intent.get("actionable", True):
            print(f"👋 Returning greeting response")
            return CleanResponseBuilder.build_greeting_response(
                query=query,
                user_id=user_id,
                user_role=user_role
            )
        
        # Determine which tool to use
        tool_name = self._determine_tool(query, user_role)
        parameters = self._extract_parameters(tool_name, query, user_id)
        
        print(f"🛠️ Using tool: {tool_name} with params: {parameters}")
        
        # Execute the tool
        try:
            tool_response = self._execute_tool(tool_name, parameters)
            print(f"🔧 Tool response received: {tool_response.get('success', False)}")
            
            if not tool_response.get("success", False):
                error_msg = tool_response.get("error", "Tool execution failed")
                print(f"❌ Tool failed: {error_msg}")
                return CleanResponseBuilder.build_error_response(
                    query=query,
                    user_id=user_id,
                    user_role=user_role,
                    error_message=error_msg,
                    tool_used=tool_name,
                    tool_parameters=parameters
                )
            
            result = tool_response.get("result", {})
            print(f"✅ Tool result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
            
            # Prepare response based on tool and role
            response = self._prepare_final_response(
                tool_name=tool_name,
                result=result,
                query=query,
                user_id=user_id,
                user_role=user_role,
                parameters=parameters,
                intent=intent["intent"]
            )
            
            print(f"✅ Response built successfully. Data type: {tool_name}")
            return response
            
        except Exception as e:
            print(f"❌ Error in process_query: {e}")
            import traceback
            traceback.print_exc()
            
            return CleanResponseBuilder.build_error_response(
                query=query,
                user_id=user_id,
                user_role=user_role,
                error_message=f"Processing error: {str(e)}",
                tool_used=tool_name,
                tool_parameters=parameters
            )
    def _prepare_final_response(self, tool_name, result, query, user_id, user_role, parameters, intent):
        """Prepare final response based on tool and role"""
        
        # Determine data type for response
        data_type = tool_name
        
        # Prepare data based on tool
        if tool_name == "get_daily_productivity":
            # For daily productivity, return structured data
            productivity_data = result.get("data", [])
            
            if productivity_data and len(productivity_data) > 0:
                # Calculate summary
                total_productive = sum(item.get("productive_hours", 0) for item in productivity_data)
                total_idle = sum(item.get("idle_hours", 0) for item in productivity_data)
                total_hours = total_productive + total_idle
                avg_productivity = (total_productive / total_hours * 100) if total_hours > 0 else 0
                
                latest_day = productivity_data[-1] if productivity_data else {}
            else:
                latest_day = {}
                total_productive = total_idle = total_hours = avg_productivity = 0
            
            data = {
                "user_id": user_id,
                "period_days": parameters.get("days", 7),
                "productivity_data": productivity_data,
                "latest_day": latest_day,
                "summary": {
                    "total_productive_hours": round(total_productive, 2),
                    "total_idle_hours": round(total_idle, 2),
                    "total_hours": round(total_hours, 2),
                    "average_productivity": round(avg_productivity, 2),
                    "days_analyzed": len(productivity_data)
                },
                "message": "Daily productivity analysis completed" if user_role == "user" else "Manager personal productivity analysis"
            }
            
        elif tool_name == "get_team_productivity":
            # For team productivity, include team data
            team_data = result.get("team_data", [])
            summary = result.get("summary", {})
            
            data = {
                "manager_id": user_id,
                "period_days": parameters.get("days", 7),
                "team_data": team_data,
                "summary": summary,
                "has_data": result.get("has_data", False),
                "top_performers": sorted(team_data, key=lambda x: x.get("productivity_score", 0), reverse=True)[:3] if team_data else [],
                "needs_attention": sorted(team_data, key=lambda x: x.get("productivity_score", 0))[:3] if team_data else [],
                "message": f"Team productivity analysis for {len(team_data)} members"
            }
            
        elif tool_name == "get_team_idle_analysis":
            # For team idle analysis
            team_members = result.get("team_members", [])
            summary = result.get("summary", {})
            
            data = {
                "manager_id": user_id,
                "period_days": parameters.get("days", 30),
                "team_members": team_members,
                "summary": summary,
                "has_data": result.get("has_data", False),
                "highest_idle": sorted(team_members, key=lambda x: x.get("idle_percentage", 0), reverse=True)[:3] if team_members else [],
                "message": f"Team idle analysis for {len(team_members)} members"
            }
            
        elif tool_name == "analyze_idle_patterns":
            # For individual idle analysis
            idle_percentage = result.get("idle_percentage", 0)
            idle_count = result.get("idle_count", 0)
            total_activities = result.get("total_activities", 0)
            common_times = result.get("common_idle_times", [])
            
            # Generate meaningful message
            if total_activities == 0:
                message = "No activity data found for idle analysis"
            elif idle_count == 0:
                message = "Excellent! No idle periods detected in recent activity"
            else:
                message = f"Idle analysis: {idle_percentage:.1f}% of activities were idle ({idle_count}/{total_activities})"
                if common_times:
                    message += f". Common idle times: {', '.join(common_times[:3])}"
            
            data = {
                "user_id": user_id,
                "idle_analysis": result,
                "summary": {
                    "idle_percentage": idle_percentage,
                    "idle_count": idle_count,
                    "total_activities": total_activities,
                    "common_idle_times": common_times,
                    "has_data": result.get("has_data", False)
                },
                "message": message
            }
            
        elif tool_name == "generate_manager_report":
            data = result
            
        else:
            # Default case
            data = result
        
        # Use the build_response_with_copy_feature method
        return CleanResponseBuilder.build_response_with_copy_feature(
            success=True,
            data_type=data_type,
            query=query,
            user_id=user_id,
            user_role=user_role,
            tool_used=tool_name,
            tool_parameters=parameters,
            intent=intent,
            data=data
        )
    def _prepare_visualization_data(self, tool_response, tool_name):
        """Prepare visualization data based on tool response"""
        if not tool_response.get("result"):
            return None
        
        result = tool_response["result"]
        
        if tool_name == "get_daily_productivity":
            # Format for daily productivity chart
            return result  # Already has date, productive_hours, etc.
        
        elif tool_name == "get_team_productivity":
            # Format team data for visualization
            team_data = result.get("team_data", [])
            visualization_data = []
            for member in team_data:
                visualization_data.append({
                    "name": member.get("name", "Unknown"),
                    "productivity_score": member.get("productivity_score", 0),
                    "productive_hours": member.get("productive_hours", 0),
                    "idle_hours": member.get("idle_hours", 0)
                })
            return visualization_data
        
        elif tool_name == "get_team_idle_analysis":
            # Format idle analysis data
            team_members = result.get("team_members", [])
            visualization_data = []
            for member in team_members:
                visualization_data.append({
                    "name": member.get("name", "Unknown"),
                    "idle_percentage": member.get("idle_percentage", 0),
                    "idle_count": member.get("idle_count", 0)
                })
            return visualization_data
        
        return None