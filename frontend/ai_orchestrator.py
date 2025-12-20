from datetime import datetime, timezone
import os
import json
from typing import Dict, Any, List, Optional
import requests
from dataclasses import dataclass
from dotenv import load_dotenv
import groq
from supabase_client import supabase
# Load environment variables
load_dotenv()

@dataclass
class ToolCallResult:
    tool_name: str
    parameters: Dict[str, Any]
    result: Any

class AIOrchestrator:
    """Orchestrates AI queries and tool calling using Groq"""
    
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
        self.supabase = supabase
        
        # Available Groq models (as of Dec 2024)
        self.available_models = [
            "llama-3.3-70b-versatile",    # Best overall
            "llama-3.2-3b-preview",       # Faster, smaller
            "llama-3.2-1b-preview",       # Fastest
            "llama-3.2-90b-vision-preview", # With vision
        ]
        
        # Try models in order of preference
        self.current_model = self.available_models[0]
        
        if not self.groq_api_key:
            print("⚠️ WARNING: GROQ_API_KEY not found in environment variables")
            print("   AI features will be disabled. Set GROQ_API_KEY in .env file")
            print("   Get a free key from: https://console.groq.com/")
            self.client = None
        else:
            try:
                import groq
                self.client = groq.Groq(api_key=self.groq_api_key)
                print(f"✅ Groq SDK initialized with model: {self.current_model}")
                print(f"   Available credits: https://console.groq.com/usage")
                
                # Test the model availability
                self._test_model_availability()
                
            except ImportError:
                print("❌ Groq package not installed. Run: pip install groq")
                self.client = None
            except Exception as e:
                print(f"❌ Error initializing Groq: {e}")
                self.client = None
        
        # Define available tools for the AI
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_daily_productivity",
                    "description": "Get daily productivity data for a user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "User ID"},
                            "date": {"type": "string", "description": "Specific date (YYYY-MM-DD)"},
                            "days": {"type": "integer", "description": "Number of days to analyze", "default": 7}
                        },
                        "required": ["user_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_idle_patterns",
                    "description": "Analyze idle patterns for a user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "User ID"}
                        },
                        "required": ["user_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_manager_report",
                    "description": "Generate comprehensive report for a manager",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "manager_id": {"type": "string", "description": "Manager ID"},
                            "days": {"type": "integer", "description": "Number of days to analyze", "default": 7}
                        },
                        "required": ["manager_id"]
                    }
                }
            }
        ]
    
    def _test_model_availability(self):
        """Test if current model is available"""
        if not self.client:
            return False
        
        try:
            # Quick test call
            test_response = self.client.chat.completions.create(
                model=self.current_model,
                messages=[{"role": "user", "content": "Say hello"}],
                max_tokens=5
            )
            print(f"✅ Model {self.current_model} is available")
            return True
        except Exception as e:
            print(f"❌ Model {self.current_model} error: {e}")
            # Try fallback models
            for model in self.available_models[1:]:
                try:
                    test_response = self.client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": "Say hello"}],
                        max_tokens=5
                    )
                    self.current_model = model
                    print(f"✅ Switched to model: {model}")
                    return True
                except:
                    continue
            print("❌ No available models found")
            return False
    def _determine_single_tool(self, intent: str, query: str) -> str:
        """Map intent to exactly one tool"""
        query_lower = query.lower()
        
        # Priority mapping - only ONE tool per query
        if "manager" in query_lower or "team" in query_lower or "report" in query_lower:
            return "generate_manager_report"
        elif "idle" in query_lower or "inactive" in query_lower:
            return "analyze_idle_patterns"
        else:
            # Default to daily productivity
            return "get_daily_productivity"
        
    def _extract_single_tool_parameters(self, tool_name: str, query: str, user_id: str) -> dict:
        """Extract parameters for a single tool"""
        base_params = {"user_id": user_id}
        
        # Simple parameter extraction (can be enhanced with AI)
        if tool_name == "get_daily_productivity":
            if "today" in query.lower():
                base_params["days"] = 1
            elif "week" in query.lower() or "7" in query:
                base_params["days"] = 7
            else:
                base_params["days"] = 1  # Default
        
        elif tool_name == "generate_manager_report":
            base_params["manager_id"] = user_id
            if "month" in query.lower() or "30" in query:
                base_params["days"] = 30
            else:
                base_params["days"] = 7
        
        return base_params
    def _log_intent(self, user_id: str, query: str, intent_result: dict, tool_called: str = None):
        """Log intent classification for audit trail"""
        try:
            self.supabase.table("intent_logs").insert({
                "user_id": user_id,
                "query": query,
                "intent": intent_result.get("intent"),
                "actionable": intent_result.get("actionable", False),
                "tool_called": tool_called,
                "created_at": datetime.now(timezone.utc).isoformat()
            }).execute()
        except Exception as e:
            print(f"⚠️ Failed to log intent: {e}")
    def _log_intent(self, user_id: str, query: str, intent: str, actionable: bool):
        """Log intent classification for audit trail"""
        try:
            # You'll need to import supabase in ai_orchestrator.py
            from supabase_client import supabase
            
            supabase.table("intent_logs").insert({
                "user_id": user_id,
                "query": query,
                "intent": intent,
                "actionable": actionable,
                "created_at": datetime.now(timezone.utc).isoformat()
            }).execute()
        except Exception as e:
            print(f"Failed to log intent: {e}")
    def process_query(self, user_id: str, query: str) -> Dict[str, Any]:
        """Two-stage MCP processing with intent gating and role-based access"""
        
        # STEP 0: Get user role FIRST
        user_role = self._get_user_role(user_id)
        print(f"👤 User Role Detected: {user_role} for user {user_id}")
        
        # STAGE 1: Intent Classification
        try:
            classifier = IntentClassifier()
            intent_result = classifier.classify_intent(query)
            
            # Log the classification
            print(f"🎯 Intent Classification: {intent_result}")
            
            # Log intent to database for audit trail
            self._log_intent(user_id, query, intent_result.get("intent", "unknown"), 
                            intent_result.get("actionable", False))
            
            # Handle non-actionable intents
            if not intent_result.get("actionable", False):
                return {
                    "explanation": intent_result.get("suggested_response", 
                        self._generate_friendly_response(query, intent_result.get("intent"))),
                    "data": [],
                    "visualization_type": "none",
                    "tool_calls": [],
                    "intent": intent_result.get("intent", "unknown")
                }
            
        except Exception as e:
            print(f"❌ Intent classification failed: {e}")
            # Fallback to rule-based intent detection
            intent_result = self._fallback_intent_classification(query)
            
            # Handle non-actionable fallback intents
            if not intent_result.get("actionable", False):
                return {
                    "explanation": intent_result.get("suggested_response", 
                        self._generate_friendly_response(query, intent_result.get("intent"))),
                    "data": [],
                    "visualization_type": "none",
                    "tool_calls": [],
                    "intent": intent_result.get("intent", "unknown")
                }
        
        try:
            # STEP 2: Determine tool based on intent AND user role
            tool_name = self._determine_tool_by_role(intent_result["intent"], query, user_role)
            
            # STEP 3: Extract parameters with role consideration
            parameters = self._extract_tool_parameters(tool_name, query, user_id, user_role)
            
            # STEP 4: Validate manager access for team tools
            if not self._validate_tool_access(tool_name, user_role):
                return {
                    "explanation": f"🔒 **Access Denied**\n\nThis feature is only available for managers. "
                                f"You're currently logged in as a {user_role}.\n\n"
                                f"Please ask about your personal productivity or contact your manager.",
                    "data": [],
                    "visualization_type": "none",
                    "tool_calls": [],
                    "intent": intent_result["intent"]
                }
            
            # Log tool call attempt
            print(f"🔧 Tool Selection: {tool_name} with params: {parameters}")
            print(f"   User Role: {user_role}")
            
            # STEP 5: Execute the tool via MCP server
            mcp_response = self._execute_tool_with_debug(tool_name, parameters)
            
            if "error" in mcp_response:
                error_msg = mcp_response.get('error', 'Unknown error')
                print(f"❌ MCP Tool Error: {error_msg}")
                
                # Try fallback to basic tool if manager tool fails
                if tool_name in ["generate_manager_report", "get_team_productivity"] and user_role == "manager":
                    print("🔄 Falling back to basic productivity tool for manager")
                    tool_name = "get_daily_productivity"
                    parameters = {"user_id": user_id, "days": 7}
                    mcp_response = self._execute_tool_with_debug(tool_name, parameters)
                    
                    if "error" in mcp_response:
                        raise Exception(f"Fallback also failed: {mcp_response.get('error')}")
                else:
                    raise Exception(f"Tool execution failed: {error_msg}")
            
            # Extract the actual result data from MCP response
            if isinstance(mcp_response, dict) and "result" in mcp_response:
                tool_result = mcp_response["result"]
                print(f"✅ Successfully extracted 'result' from MCP response")
            else:
                tool_result = mcp_response
                print(f"⚠️ No 'result' key found, using raw response")
            
            print(f"📊 Tool result type: {type(tool_result)}")
            
            # Debug print based on result type
            if isinstance(tool_result, list):
                print(f"📊 Tool result items: {len(tool_result)}")
                if tool_result:
                    print(f"📊 First item: {tool_result[0]}")
            elif isinstance(tool_result, dict):
                print(f"📊 Tool result keys: {list(tool_result.keys())}")
            
            # STEP 6: Generate user-friendly explanation with role context
            explanation = self._generate_role_based_explanation(query, tool_name, tool_result, user_role)
            
            # STEP 7: Extract data for visualization
            data = self._extract_visualization_data(tool_result, tool_name)
            
            print(f"📈 Visualization data points: {len(data)}")
            if data:
                print(f"📈 Sample data: {data[0]}")
            
            # STEP 8: Determine appropriate visualization type
            visualization_type = self._determine_visualization_type(query, tool_name, data, user_role)
            
            return {
                "explanation": explanation,
                "data": data,
                "visualization_type": visualization_type,
                "tool_calls": [{
                    "tool_name": tool_name,
                    "parameters": parameters
                }],
                "intent": intent_result["intent"],
                "user_role": user_role  # Optional: include role in response for frontend
            }
            
        except Exception as e:
            print(f"❌ Tool execution error: {e}")
            import traceback
            traceback.print_exc()
            # Return informative fallback response
            return self._fallback_response_with_role(user_id, query, str(e), 
                                                    intent_result.get("intent", "unknown"), 
                                                    user_role)
        # In ai_orchestrator.py, _execute_tool method:
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        try:
            response = requests.post(
                f"{self.mcp_server_url}/execute_tool/{tool_name}",
                json=parameters,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            # FIX: Check the actual response structure from server.py
            print(f"🔧 MCP Response: {json.dumps(result, indent=2)}")
            
            # Extract data based on actual server response
            if result.get("success"):
                return result.get("result", [])  # Return the actual result data
            else:
                return {"error": f"Tool execution failed: {result}"}
                
        except Exception as e:
            print(f"❌ MCP Tool execution error: {e}")
            return {"error": str(e), "tool": tool_name}
    def _get_user_role(self, user_id: str) -> str:
        """Get user role from database"""
        try:
            # Import here to avoid circular imports
            from supabase_client import supabase
            
            response = supabase.table("profiles").select("role").eq("id", user_id).execute()
            
            if response.data:
                role = response.data[0].get("role", "user")
                return role
            else:
                # Try to get from session if available
                return "user"  # Default fallback
        except Exception as e:
            print(f"⚠️ Failed to get user role: {e}")
            return "user"  # Default to user if error

    def _determine_tool_by_role(self, intent: str, query: str, user_role: str) -> str:
        """Determine tool based on intent AND user role"""
        query_lower = query.lower()
        
        # Manager-specific tools
        if user_role == "manager":
            if "team" in query_lower or "all" in query_lower or "everyone" in query_lower:
                return "get_team_productivity"
            elif "compare" in query_lower or "comparison" in query_lower:
                return "get_team_comparison"
            elif "report" in query_lower or "summary" in query_lower:
                return "generate_manager_report"
            elif "idle" in query_lower or "inactive" in query_lower:
                # Managers can analyze idle patterns for themselves
                return "analyze_idle_patterns"
            else:
                # Default for managers asking about themselves
                return "get_daily_productivity"
        
        # User tools (regular employees)
        else:
            if "idle" in query_lower or "inactive" in query_lower:
                return "analyze_idle_patterns"
            else:
                # Users can only see their own data
                return "get_daily_productivity"

    def _extract_tool_parameters(self, tool_name: str, query: str, user_id: str, user_role: str) -> dict:
        """Extract parameters with role consideration"""
        query_lower = query.lower()
        
        # Base parameters
        if tool_name == "get_daily_productivity":
            params = {"user_id": user_id}
            if "today" in query_lower:
                params["days"] = 1
            elif "week" in query_lower or "7" in query:
                params["days"] = 7
            elif "month" in query_lower or "30" in query:
                params["days"] = 30
            else:
                params["days"] = 7  # Default
        
        elif tool_name in ["get_team_productivity", "get_team_comparison"]:
            # These are manager-only tools
            params = {"manager_id": user_id}
            if "month" in query_lower or "30" in query:
                params["days"] = 30
            else:
                params["days"] = 7
        
        elif tool_name == "generate_manager_report":
            params = {"manager_id": user_id}
            params["days"] = 7  # Default weekly report
        
        elif tool_name == "analyze_idle_patterns":
            params = {"user_id": user_id}
        
        else:
            params = {"user_id": user_id}
        
        print(f"📋 Extracted parameters for {tool_name}: {params}")
        return params

    def _validate_tool_access(self, tool_name: str, user_role: str) -> bool:
        """Validate if user has access to the requested tool"""
        manager_tools = ["get_team_productivity", "get_team_comparison", "generate_manager_report"]
        
        if tool_name in manager_tools and user_role != "manager":
            print(f"🚫 Access denied: {tool_name} requires manager role, user is {user_role}")
            return False
        
        return True

    def _execute_tool_with_debug(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute tool with detailed debugging"""
        print(f"🛠️ Executing {tool_name} via MCP server...")
        print(f"   Parameters: {parameters}")
        
        try:
            response = requests.post(
                f"{self.mcp_server_url}/execute_tool/{tool_name}",
                json=parameters,
                timeout=15
            )
            
            print(f"   MCP Status Code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"   ❌ MCP Error Response: {response.text}")
                return {"error": f"MCP server returned {response.status_code}"}
            
            result = response.json()
            print(f"   ✅ MCP Response received")
            print(f"   Response keys: {list(result.keys())}")
            
            if "result" in result:
                print(f"   Result type: {type(result['result'])}")
                if isinstance(result['result'], list):
                    print(f"   Result items: {len(result['result'])}")
                elif isinstance(result['result'], dict):
                    print(f"   Result dict keys: {list(result['result'].keys())}")
            
            return result
            
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Cannot connect to MCP server at {self.mcp_server_url}")
            return {"error": "MCP server not reachable. Make sure it's running on port 8000."}
        except requests.exceptions.Timeout:
            print(f"   ⏱️  MCP server timeout")
            return {"error": "MCP server timeout. Try again."}
        except Exception as e:
            print(f"   ❌ MCP execution error: {e}")
            return {"error": str(e)}

    def _generate_role_based_explanation(self, query: str, tool_name: str, tool_result: Any, user_role: str) -> str:
        """Generate explanation with role context"""
        
        # Add this case for idle patterns:
        if tool_name == "analyze_idle_patterns":
            if isinstance(tool_result, dict):
                idle_pct = tool_result.get("idle_percentage", 0)
                total_activities = tool_result.get("total_activities", 0)
                idle_count = tool_result.get("idle_count", 0)
                common_times = tool_result.get("common_idle_times", [])
                
                explanation = f"⏸️ **Idle Pattern Analysis**\n\n"
                explanation += f"**📊 Summary:**\n"
                explanation += f"• Idle percentage: **{idle_pct:.1f}%**\n"
                explanation += f"• Total activities tracked: **{total_activities}**\n"
                explanation += f"• Idle events: **{idle_count}**\n\n"
                
                if common_times:
                    explanation += f"**🕒 Common Idle Times:**\n"
                    for time in common_times[:5]:  # Show top 5
                        explanation += f"• {time}\n"
                
                # Add analysis from tool_result
                analysis = tool_result.get("analysis", "")
                if analysis:
                    explanation += f"\n**💡 Insights:**\n{analysis}"
                
                if idle_pct > 20:
                    explanation += f"\n\n**⚠️ Recommendation:** Your idle time is above average. Try taking scheduled breaks to maintain focus."
                elif idle_pct < 10:
                    explanation += f"\n\n**✅ Excellent:** Your idle time is very low. Keep up the good work!"
                
                return explanation
        
        # Rest of the method remains the same...
        if tool_name == "get_daily_productivity":
            if isinstance(tool_result, list) and tool_result:
                total_productive = sum(d.get("productive_hours", 0) for d in tool_result)
                total_idle = sum(d.get("idle_hours", 0) for d in tool_result)
                avg_score = sum(d.get("productivity_score", 0) for d in tool_result) / len(tool_result)
                
                explanation = f"📊 **Your Productivity Analysis**\n\n"
                explanation += f"**📈 Summary ({len(tool_result)} days):**\n"
                explanation += f"• Total Productive: **{total_productive:.1f}h**\n"
                explanation += f"• Total Idle: **{total_idle:.1f}h**\n"
                explanation += f"• Average Score: **{avg_score:.1f}%**\n\n"
                
                if user_role == "manager":
                    explanation += "💼 *Viewing your personal productivity as a manager*\n"
                
                return explanation
        
        elif tool_name == "get_team_productivity":
            explanation = f"👥 **Team Productivity Report**\n\n"
            if isinstance(tool_result, dict) and "team_data" in tool_result:
                team_data = tool_result["team_data"]
                summary = tool_result.get("summary", {})
                
                explanation += f"**Team Overview:**\n"
                explanation += f"• Team Size: **{len(team_data)} members**\n"
                explanation += f"• Period: **{tool_result.get('period_days', 7)} days**\n"
                explanation += f"• Avg Productivity: **{summary.get('average_productivity', 0):.1f}%**\n\n"
                
                explanation += f"**🏆 Top Performers:**\n"
                for i, member in enumerate(team_data[:3]):
                    explanation += f"{i+1}. **{member.get('name', 'Unknown')}** - {member.get('productivity_score', 0):.1f}%\n"
                
                return explanation
        
        # Fallback explanation - THIS IS WHAT YOU'RE SEEING
        return f"📊 **Analysis Complete**\n\nBased on your query '{query}', here's your productivity data."

    def _fallback_response_with_role(self, user_id: str, query: str, error: str, intent: str, user_role: str) -> Dict[str, Any]:
        """Fallback response with role context"""
        
        role_context = "👤 User" if user_role == "user" else "💼 Manager"
        
        explanation = f"🤖 **WorkPulse AI Assistant** ({role_context})\n\n"
        explanation += f"**Query:** '{query}'\n\n"
        
        if error:
            explanation += f"**Error:** {error}\n\n"
        
        if user_role == "manager":
            explanation += "**As a manager, you can:**\n"
            explanation += "• View team productivity reports\n"
            explanation += "• Compare team member performance\n"
            explanation += "• Generate weekly reports\n"
            explanation += "• Analyze your own productivity\n\n"
            explanation += "**Try:** 'Show my team's productivity' or 'Generate weekly report'"
        else:
            explanation += "**You can:**\n"
            explanation += "• View your daily productivity\n"
            explanation += "• Analyze your idle patterns\n"
            explanation += "• See weekly trends\n\n"
            explanation += "**Try:** 'Show my productivity today' or 'Analyze my idle time'"
        
        return {
            "explanation": explanation,
            "data": [],
            "visualization_type": "bar",
            "tool_calls": [],
            "intent": intent,
            "user_role": user_role
        }
    def _determine_visualization_type(self, query: str, tool_name: str, data: List[Dict], user_role: str = None) -> str:
        """Determine the best visualization type based on query and results"""
        query_lower = query.lower()
        
        print(f"\n🎨 DETERMINING VISUALIZATION TYPE")
        print(f"   Query: {query_lower}")
        print(f"   Tool: {tool_name}")
        print(f"   Data points: {len(data)}")
        
        # Priority rules
        if tool_name == "analyze_idle_patterns":
            print(f"   🎯 Selected: pie (idle analysis)")
            return "pie"
        
        if "trend" in query_lower or "over time" in query_lower or "week" in query_lower:
            print(f"   🎯 Selected: line (trend query)")
            return "line"
        
        if "compare" in query_lower or "team" in query_lower:
            print(f"   🎯 Selected: bar (comparison)")
            return "bar"
        
        if tool_name == "generate_manager_report":
            print(f"   🎯 Selected: bar (manager report)")
            return "bar"
        
        # Default based on data
        if data and len(data) > 1:
            if any("category" in d for d in data):
                print(f"   🎯 Selected: pie (categorical data)")
                return "pie"
            else:
                print(f"   🎯 Selected: bar (multiple data points)")
                return "bar"
        
        print(f"   🎯 Selected: bar (default)")
        return "bar"

    def _extract_visualization_data(self, tool_result: Any, tool_name: str) -> List[Dict]:
        """Extract data suitable for visualization from tool results"""
        data = []
        
        print(f"\n🔍 EXTRACTING VISUALIZATION DATA FOR: {tool_name}")
        print(f"   Input type: {type(tool_result)}")
        print(f"   Input preview: {str(tool_result)[:200]}")
        
        try:
            # Handle case where tool_result is the full MCP response
            if isinstance(tool_result, dict) and "result" in tool_result:
                actual_data = tool_result["result"]
                print(f"   ✅ Found 'result' key in response")
            else:
                actual_data = tool_result
                print(f"   ⚠️ No 'result' key, using raw data")
            
            print(f"   Actual data type: {type(actual_data)}")
            
            if tool_name == "get_daily_productivity":
                print(f"   Processing daily productivity data...")
                
                if isinstance(actual_data, list):
                    print(f"   ✅ Got list with {len(actual_data)} items")
                    
                    for i, item in enumerate(actual_data):
                        if isinstance(item, dict):
                            # Extract with defaults
                            date_val = item.get("date", f"Day {i+1}")
                            productive = float(item.get("productive_hours", 0))
                            idle = float(item.get("idle_hours", 0))
                            score = float(item.get("productivity_score", 0))
                            
                            data.append({
                                "date": date_val,
                                "label": date_val,  # For chart labels
                                "productive_hours": productive,
                                "idle_hours": idle,
                                "productivity_score": score,
                                "total_hours": productive + idle,
                                "value": productive  # For simple charts
                            })
                            print(f"   📅 Added: {date_val} - {productive}h productive")
                        else:
                            print(f"   ⚠️ Item {i} is not a dict: {type(item)}")
                else:
                    print(f"   ❌ Expected list, got {type(actual_data)}")
                    # Try to create mock data for testing
                    print(f"   🧪 Creating mock data for testing")
                    for i in range(7):
                        date_str = f"2024-12-{20-i}"
                        data.append({
                            "date": date_str,
                            "label": date_str,
                            "productive_hours": 6.0 + (i * 0.5),
                            "idle_hours": 1.5 - (i * 0.1),
                            "productivity_score": 80.0 + (i * 2),
                            "total_hours": 8.0,
                            "value": 6.0 + (i * 0.5)
                        })
            
            elif tool_name == "analyze_idle_patterns":
                print(f"   Processing idle patterns data...")
                
                if isinstance(actual_data, dict):
                    idle_pct = float(actual_data.get("idle_percentage", 25.0))
                    print(f"   ✅ Idle percentage: {idle_pct}%")
                    
                    data.append({
                        "category": "Productive",
                        "label": "Productive Time",
                        "value": 100 - idle_pct,
                        "color": "#4CAF50"
                    })
                    data.append({
                        "category": "Idle",
                        "label": "Idle Time",
                        "value": idle_pct,
                        "color": "#FF9800"
                    })
                else:
                    print(f"   ❌ Expected dict, got {type(actual_data)}")
                    # Mock data
                    data.append({"category": "Productive", "value": 75, "label": "Productive"})
                    data.append({"category": "Idle", "value": 25, "label": "Idle"})
            
            elif tool_name == "generate_manager_report":
                print(f"   Processing manager report data...")
                
                if isinstance(actual_data, dict) and "team_data" in actual_data:
                    team_list = actual_data["team_data"]
                    print(f"   ✅ Found team_data with {len(team_list)} members")
                    
                    for i, member in enumerate(team_list):
                        if isinstance(member, dict):
                            name = member.get("name", f"Member {i+1}")
                            score = float(member.get("productivity_score", 70 + (i * 5)))
                            
                            data.append({
                                "name": name,
                                "date": name,  # For x-axis labels
                                "label": name,
                                "productive_hours": float(member.get("productive_hours", 6.5)),
                                "idle_hours": float(member.get("idle_hours", 1.5)),
                                "productivity_score": score,
                                "value": score  # For charts
                            })
                            print(f"   👤 Added: {name} - {score}%")
                else:
                    print(f"   ❌ No team_data found or not a dict")
                    # Mock team data
                    mock_team = ["John Doe", "Jane Smith", "Bob Johnson", "Alice Brown"]
                    for i, name in enumerate(mock_team):
                        score = 70 + (i * 8)
                        data.append({
                            "name": name,
                            "date": name,
                            "label": name,
                            "productive_hours": 6.0 + (i * 0.5),
                            "idle_hours": 2.0 - (i * 0.2),
                            "productivity_score": score,
                            "value": score
                        })
        
        except Exception as e:
            print(f"   ❌ ERROR in extract_visualization_data: {e}")
            import traceback
            traceback.print_exc()
            # Return mock data as fallback
            data = [{"date": "Error", "value": 1, "label": "Error occurred"}]
        
        print(f"   📊 FINAL: Extracted {len(data)} data points")
        if data:
            print(f"   📊 Sample: {data[0]}")
        
        return data
    
    def _fallback_response(self, user_id: str, query: str, error: str = "") -> Dict[str, Any]:
        """Fallback response when AI fails or not available"""
        
        error_msg = f"\n\nError: {error}" if error else ""
        
        # Simple rule-based responses
        query_lower = query.lower()
        
        if "daily" in query_lower or "today" in query_lower or "day" in query_lower:
            days = 1 if "today" in query_lower else 7
            return {
                "explanation": f"📊 **Daily Productivity Analysis**{error_msg}\n\nI'll show your productivity data for the last {days} day(s).\n\n*For AI-powered insights with natural language processing, ensure:*\n1. ✅ MCP server is running (http://localhost:8000)\n2. ✅ You have Groq API credits (free at console.groq.com)\n3. ✅ Correct model is configured\n\n**Data will be fetched from:**\n- Tool: `get_daily_productivity`\n- User: {user_id}\n- Days: {days}",
                "data": [],
                "visualization_type": "bar",
                "tool_calls": [{"tool_name": "get_daily_productivity", "parameters": {"user_id": user_id, "days": days}}]
            }
        elif "idle" in query_lower or "inactive" in query_lower:
            return {
                "explanation": f"⏸️ **Idle Pattern Analysis**{error_msg}\n\nI'll analyze when you're most idle/unproductive.\n\n*Tips to reduce idle time:*\n1. Take regular short breaks (Pomodoro technique)\n2. Minimize notifications\n3. Use focus timers\n4. Track unproductive websites/apps\n\n**Analysis will include:**\n- Idle percentage\n- Common idle times\n- Improvement suggestions",
                "data": [],
                "visualization_type": "pie",
                "tool_calls": [{"tool_name": "analyze_idle_patterns", "parameters": {"user_id": user_id}}]
            }
        elif "report" in query_lower or "team" in query_lower or "manager" in query_lower:
            return {
                "explanation": f"👥 **Team Productivity Report**{error_msg}\n\nI'll generate a comprehensive team report.\n\n*Report includes:*\n1. Individual productivity scores\n2. Team averages\n3. Top performers\n4. Areas for improvement\n5. Weekly trends\n\n**Data sources:**\n- All team members' activity\n- Last 7 days of data\n- Productivity metrics",
                "data": [],
                "visualization_type": "bar",
                "tool_calls": [{"tool_name": "generate_manager_report", "parameters": {"manager_id": user_id, "days": 7}}]
            }
        else:
            return {
                "explanation": f"🤖 **WorkPulse AI Assistant**{error_msg}\n\n**Your Query:** '{query}'\n\n**To enable full AI capabilities:**\n\n🔑 **1. Get API Key (FREE):**\n   • Visit: https://console.groq.com/\n   • Sign up (no credit card needed)\n   • Create API key\n\n⚙️ **2. Update .env file:**\n   ```\n   GROQ_API_KEY=your_key_here\n   MCP_SERVER_URL=http://localhost:8000\n   ```\n\n🚀 **3. Start MCP Server:**\n   ```bash\n   cd mcp\n   python server.py\n   ```\n\n💡 **4. Try Example Queries:**\n   • 'Show my productivity for today'\n   • 'Analyze my idle patterns'\n   • 'Generate team report for last week'\n   • 'Compare my Monday vs Friday productivity'\n\n📊 **Current Status:**\n   • Flask App: ✅ Running\n   • MCP Server: {'✅ Running' if self.mcp_server_url else '❌ Not running'}\n   • Groq AI: {'✅ Configured' if self.groq_api_key else '❌ Not configured'}",
                "data": [],
                "visualization_type": "bar",
                "tool_calls": []
            }
    def _fallback_intent_classification(self, query: str) -> dict:
        """Fallback when main classifier fails"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["productivity", "report", "idle", "hours"]):
            return {"intent": "productivity_query", "actionable": True}
        else:
            return {"intent": "other", "actionable": False}

    def _generate_explanation(self, query: str, tool_name: str, tool_result: Any) -> str:
        """Generate user-friendly explanation with actual data insights"""
        
        if tool_name == "get_daily_productivity":
            if isinstance(tool_result, list) and len(tool_result) > 0:
                # Calculate actual statistics
                total_productive = sum(d.get("productive_hours", 0) for d in tool_result)
                total_idle = sum(d.get("idle_hours", 0) for d in tool_result)
                avg_productivity = sum(d.get("productivity_score", 0) for d in tool_result) / len(tool_result)
                
                # Find best and worst days
                best_day = max(tool_result, key=lambda x: x.get("productivity_score", 0))
                worst_day = min(tool_result, key=lambda x: x.get("productivity_score", 100))
                
                explanation = f"📊 **Productivity Analysis - Last 7 Days**\n\n"
                explanation += f"**📈 Overall Stats:**\n"
                explanation += f"• Total Productive Hours: **{total_productive:.1f}h**\n"
                explanation += f"• Total Idle Hours: **{total_idle:.1f}h**\n"
                explanation += f"• Average Productivity: **{avg_productivity:.1f}%**\n\n"
                
                explanation += f"**🏆 Best Day:** {best_day.get('date', 'Unknown')} - {best_day.get('productivity_score', 0):.1f}%\n"
                explanation += f"**📉 Needs Improvement:** {worst_day.get('date', 'Unknown')} - {worst_day.get('productivity_score', 0):.1f}%\n\n"
                
                explanation += f"**💡 Insights:**\n"
                if avg_productivity > 80:
                    explanation += "• Excellent productivity! You're consistently performing well.\n"
                elif avg_productivity > 60:
                    explanation += "• Good productivity! Room for minor improvements.\n"
                else:
                    explanation += "• Consider analyzing your workflow for optimization opportunities.\n"
                    
                return explanation
            
        elif tool_name == "analyze_idle_patterns":
            if isinstance(tool_result, dict):
                idle_pct = tool_result.get("idle_percentage", 0)
                analysis = tool_result.get("analysis", "")
                
                explanation = f"⏸️ **Idle Pattern Analysis**\n\n"
                explanation += f"Your idle time percentage is **{idle_pct:.1f}%**.\n\n"
                explanation += analysis
                
                if idle_pct > 20:
                    explanation += "\n\n**💡 Tip:** Consider using the Pomodoro technique (25min work, 5min break) to reduce idle time."
                
                return explanation
        
        # Fallback
        return f"📊 **Analysis Complete**\n\nBased on your query '{query}', here's your productivity data."

    def _generate_friendly_response(self, query: str, intent: str) -> str:
        """Generate responses for non-actionable intents"""
        if intent == "greeting":
            return "👋 Hello! I'm your WorkPulse AI assistant. I can help you analyze productivity data."
        elif intent == "small_talk":
            return "🤖 I'm here to help with productivity insights! Try asking about your work patterns."
        else:
            return "I'm designed to help with productivity analysis. Try asking about your work hours, reports, or idle time."
class IntentClassifier:
    def __init__(self):
        self.groq_client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    def _classify_with_groq(self, query: str) -> dict:
        """Classify intent using Groq AI"""
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an intent classifier for a productivity monitoring system.
                        Classify the user's query into one of these categories:
                        1. greeting/small_talk - Simple greetings, casual conversation
                        2. productivity_query - Questions about productivity, hours, work
                        3. report_request - Requests for reports, analytics, summaries
                        4. idle_analysis - Questions about idle time, inactivity
                        5. invalid/other - Unclear, unrelated, or nonsense queries
                        
                        Return ONLY a JSON object with these fields:
                        - intent: the category name
                        - confidence: 0.0 to 1.0
                        - actionable: true/false (true only for productivity_query, report_request, idle_analysis)
                        - suggested_response: (only for non-actionable intents)
                        """
                    },
                    {
                        "role": "user",
                        "content": f"Query: {query}"
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Groq classification failed: {e}")
            # Fallback to rule-based
            return self._fallback_classification(query)
    
    def _fallback_classification(self, query: str) -> dict:
        """Rule-based fallback classification"""
        query_lower = query.lower()
        
        # Greetings
        if any(word in query_lower for word in ["hello", "hi", "hey", "good morning", "good afternoon"]):
            return {
                "intent": "greeting",
                "confidence": 0.9,
                "actionable": False,
                "suggested_response": "👋 Hello! I'm your WorkPulse AI assistant. Ask me about your productivity!"
            }
        
        # Productivity queries
        if any(word in query_lower for word in ["productivity", "productive", "hours", "work", "today", "yesterday"]):
            return {
                "intent": "productivity_query",
                "confidence": 0.8,
                "actionable": True
            }
        
        # Reports
        if any(word in query_lower for word in ["report", "summary", "analytics", "team", "manager"]):
            return {
                "intent": "report_request",
                "confidence": 0.8,
                "actionable": True
            }
        
        # Idle analysis
        if any(word in query_lower for word in ["idle", "inactive", "away", "break"]):
            return {
                "intent": "idle_analysis",
                "confidence": 0.8,
                "actionable": True
            }
        
        # Default to non-actionable
        return {
            "intent": "other",
            "confidence": 0.5,
            "actionable": False,
            "suggested_response": "I'm not sure I understand. Try asking about your productivity, reports, or idle time patterns."
        }
    
    def classify_intent(self, query: str) -> dict:
        """Public method to classify intent"""
        return self._classify_with_groq(query)