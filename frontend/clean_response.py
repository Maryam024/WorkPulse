# clean_response.py
from datetime import datetime
from typing import Dict, Any, List, Optional

class CleanResponseBuilder:
    @staticmethod
    def build_response(
        success: bool,
        data_type: str,
        query: str,
        user_id: str,
        user_role: str,
        tool_used: str,
        tool_parameters: Dict[str, Any],
        intent: str,
        data: Dict[str, Any],
        visualization_data: Optional[List] = None,
        visualization_type: str = "bar"
    ) -> Dict[str, Any]:
        """Build a clean, structured response"""
        
        # Generate human-readable summary
        summary = CleanResponseBuilder._generate_summary(data, data_type, user_role)
        
        response = {
            "success": success,
            "data_type": data_type,
            "query": query,
            "user_id": user_id[:8] + "..." if len(user_id) > 8 else user_id,
            "user_role": user_role,
            "tool_used": tool_used,
            "tool_parameters": tool_parameters,
            "intent": intent,
            "data": data,
            "visualization_data": visualization_data,
            "visualization_type": visualization_type,
            "tool_calls": [
                {
                    "tool_name": tool_used,
                    "parameters": tool_parameters
                }
            ],
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "human_readable": CleanResponseBuilder._make_human_readable(data, data_type, user_role)
        }
        
        return response
    
    @staticmethod
    def _generate_summary(data: Dict[str, Any], data_type: str, user_role: str) -> str:
        """Generate a summary based on data type"""
        if data_type == "get_daily_productivity":
            prod_data = data.get("productivity_data", [])
            if isinstance(prod_data, list):
                return f"Analyzed {len(prod_data)} days of productivity data"
            return "Daily productivity analysis completed"
        
        elif data_type == "get_team_productivity":
            team_data = data.get("team_data", [])
            summary = data.get("summary", {})
            return f"Team analysis: {len(team_data)} members, Avg productivity: {summary.get('average_productivity', 0):.1f}%"
        
        elif data_type == "get_team_idle_analysis":
            team_members = data.get("team_members", [])
            summary = data.get("summary", {})
            return f"Team idle analysis: {len(team_members)} members, Avg idle: {summary.get('average_idle_percentage', 0):.1f}%"
        
        return f"{data_type.replace('_', ' ').title()} analysis completed"
    
    @staticmethod
    def _make_human_readable(data: Dict[str, Any], data_type: str, user_role: str) -> str:
        """Create human-readable text from data"""
        if data_type == "get_daily_productivity":
            prod_data = data.get("productivity_data", [])
            if isinstance(prod_data, list) and len(prod_data) > 0:
                latest = prod_data[-1]
                date = latest.get("date", "Unknown date")
                score = latest.get("productivity_score", 0)
                productive_hours = latest.get("productive_hours", 0)
                idle_hours = latest.get("idle_hours", 0)
                
                return f"📊 **{date} Productivity**: {score:.1f}%\n- Productive: {productive_hours:.1f}h\n- Idle: {idle_hours:.1f}h"
            return "No productivity data available for this period."
        
        elif data_type == "get_team_productivity":
            team_data = data.get("team_data", [])
            summary = data.get("summary", {})
            
            if len(team_data) > 0:
                top_performer = max(team_data, key=lambda x: x.get('productivity_score', 0))
                avg_productivity = summary.get('average_productivity', 0)
                
                human_readable = f"👥 **Team Performance**\n"
                human_readable += f"- Team size: {len(team_data)} members\n"
                human_readable += f"- Average productivity: {avg_productivity:.1f}%\n"
                human_readable += f"- Top performer: {top_performer.get('name', 'Unknown')} ({top_performer.get('productivity_score', 0):.1f}%)\n\n"
                human_readable += "**Copy the JSON data below for detailed analysis:**"
                return human_readable
            return "No team data available."
        
        elif data_type == "get_team_idle_analysis":
            team_members = data.get("team_members", [])
            summary = data.get("summary", {})
            
            if len(team_members) > 0:
                highest_idle = max(team_members, key=lambda x: x.get('idle_percentage', 0))
                avg_idle = summary.get('average_idle_percentage', 0)
                
                human_readable = f"⏰ **Team Idle Analysis**\n"
                human_readable += f"- Team size: {len(team_members)} members\n"
                human_readable += f"- Average idle time: {avg_idle:.1f}%\n"
                human_readable += f"- Highest idle: {highest_idle.get('name', 'Unknown')} ({highest_idle.get('idle_percentage', 0):.1f}%)\n\n"
                human_readable += "**Copy the JSON data below for detailed analysis:**"
                return human_readable
            return "No idle data available."
        
        elif data_type == "analyze_idle_patterns":
            idle_percentage = data.get("idle_analysis", {}).get("idle_percentage", 0)
            idle_count = data.get("idle_analysis", {}).get("idle_count", 0)
            total_activities = data.get("idle_analysis", {}).get("total_activities", 0)
            
            if total_activities > 0:
                return f"⏰ **Personal Idle Analysis**\n- Idle rate: {idle_percentage:.1f}%\n- Idle events: {idle_count}/{total_activities}"
            return "No activity data found for idle analysis."
        
        return "Analysis completed successfully."
    
    @staticmethod
    def format_json_for_display(data: Dict[str, Any]) -> str:
        """Format data as pretty JSON string for display"""
        import json
        try:
            # Remove any complex objects that can't be serialized
            def clean_obj(obj):
                if isinstance(obj, dict):
                    return {k: clean_obj(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_obj(item) for item in obj]
                elif isinstance(obj, (str, int, float, bool, type(None))):
                    return obj
                else:
                    return str(obj)
            
            clean_data = clean_obj(data)
            return json.dumps(clean_data, indent=2, default=str)
        except Exception as e:
            return f"Error formatting JSON: {str(e)}"

    @staticmethod
    def build_response_with_copy_feature(
        success: bool,
        data_type: str,
        query: str,
        user_id: str,
        user_role: str,
        tool_used: str,
        tool_parameters: Dict[str, Any],
        intent: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build response with copy-friendly JSON"""
        
        # Generate human-readable summary
        summary = CleanResponseBuilder._generate_summary(data, data_type, user_role)
        
        # Format data as JSON string for copying
        json_data = CleanResponseBuilder.format_json_for_display(data)
        
        response = {
            "success": success,
            "data_type": data_type,
            "query": query,
            "user_id": user_id[:8] + "..." if len(user_id) > 8 else user_id,
            "user_role": user_role,
            "tool_used": tool_used,
            "tool_parameters": tool_parameters,
            "intent": intent,
            "data": data,
            "json_data": json_data,  # Add formatted JSON for copying
            "tool_calls": [
                {
                    "tool_name": tool_used,
                    "parameters": tool_parameters
                }
            ],
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "human_readable": CleanResponseBuilder._make_human_readable(data, data_type, user_role),
            "has_copy_feature": True  # Flag to indicate copy feature in frontend
        }
        
        return response

    @staticmethod
    def build_error_response(
        query: str,
        user_id: str,
        user_role: str,
        error_message: str,
        tool_used: str,
        tool_parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build error response"""
        return {
            "success": False,
            "error": error_message,
            "query": query,
            "user_id": user_id,
            "user_role": user_role,
            "tool_used": tool_used,
            "tool_parameters": tool_parameters,
            "timestamp": datetime.now().isoformat(),
            "human_readable": f"❌ Error: {error_message}"
        }
    
    @staticmethod
    def build_greeting_response(
        query: str,
        user_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        """Build greeting response"""
        return {
            "success": True,
            "data_type": "greeting",
            "query": query,
            "user_id": user_id[:8] + "..." if len(user_id) > 8 else user_id,
            "user_role": user_role,
            "tool_used": "none",
            "tool_parameters": {},  # Empty parameters for greeting
            "intent": "greeting",
            "data": {
                "message": "Hello! I'm your AI productivity assistant. I can help you analyze productivity data for yourself or your team.",
                "suggestions": [
                    "Show today's productivity summary",
                    "Show weekly productivity trends",
                    "Generate team productivity analysis",
                    "Analyze idle time patterns",
                    "Generate manager report"
                ]
            },
            "tool_calls": [],
            "timestamp": datetime.now().isoformat(),
            "summary": "Greeting response",
            "human_readable": "👋 Hello! How can I help you analyze your productivity today?"
        }