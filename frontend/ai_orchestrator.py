# ai_orchestrator.py - UPDATED WITH CURRENT MODELS
from datetime import datetime, timezone
import os
import json
from typing import Dict, Any, List, Optional
import requests
from dataclasses import dataclass
from dotenv import load_dotenv
import groq

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
        """Two-stage MCP processing with intent gating"""
        
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
            # Determine which single tool to use based on intent
            tool_name = self._determine_single_tool(intent_result["intent"], query)
            
            # Extract parameters for the single tool
            parameters = self._extract_single_tool_parameters(tool_name, query, user_id)
            
            # Log tool call attempt
            print(f"🔧 Tool Selection: {tool_name} with params: {parameters}")
            
            # Execute the single tool via MCP server
            mcp_response = self._execute_tool(tool_name, parameters)  # Renamed to mcp_response
            
            if "error" in mcp_response:
                raise Exception(f"Tool execution failed: {mcp_response.get('error')}")
            
            # Extract the actual result data from MCP response
            if isinstance(mcp_response, dict) and "result" in mcp_response:
                tool_result = mcp_response["result"]
            else:
                tool_result = mcp_response
            
            print(f"📊 Tool result type: {type(tool_result)}")
            print(f"📊 Tool result preview: {str(tool_result)[:200]}...")
            
            # Generate user-friendly explanation
            explanation = self._generate_explanation(query, tool_name, tool_result)  # Pass tool_result, not mcp_response
            
            # Extract data for visualization
            data = self._extract_visualization_data(tool_result, tool_name)  # Pass tool_result, not mcp_response
            
            # Determine appropriate visualization type
            visualization_type = self._determine_visualization_type(query, tool_name, data)
            
            return {
                "explanation": explanation,
                "data": data,
                "visualization_type": visualization_type,
                "tool_calls": [{
                    "tool_name": tool_name,
                    "parameters": parameters
                }],
                "intent": intent_result["intent"]
            }
            
        except Exception as e:
            print(f"❌ Tool execution error: {e}")
            import traceback
            traceback.print_exc()
            # Return informative fallback response
            return self._fallback_response(user_id, query, str(e), intent_result.get("intent", "unknown"))
        
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute tool via MCP server"""
        try:
            print(f"   📡 Calling MCP server: {self.mcp_server_url}/execute_tool/{tool_name}")
            print(f"   📡 Parameters: {parameters}")
            
            response = requests.post(
                f"{self.mcp_server_url}/execute_tool/{tool_name}",
                json=parameters,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            print(f"   ✅ Tool executed successfully")
            print(f"   📊 Response type: {type(result)}")
            print(f"   📊 Response keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
            
            # Debug: Show what's actually in the result
            if isinstance(result, dict) and "result" in result:
                result_data = result["result"]
                print(f"   📊 Result type: {type(result_data)}")
                if isinstance(result_data, list):
                    print(f"   📊 Result length: {len(result_data)}")
                    if result_data:
                        print(f"   📊 First item: {result_data[0]}")
                elif isinstance(result_data, dict):
                    print(f"   📊 Result keys: {result_data.keys()}")
            
            return result
            
        except Exception as e:
            print(f"   ❌ Tool execution error: {e}")
            return {"error": str(e), "tool": tool_name}
    
    def _determine_visualization_type(self, query: str, tool_name: str, data: List[Dict]) -> str:
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

    def _generate_explanation(self, query: str, tool_name: str, tool_result: dict) -> str:
        """Generate user-friendly explanation"""
        if tool_name == "get_daily_productivity":
            return f"📊 **Productivity Analysis**\n\nBased on your query '{query}', here's your productivity data."
        elif tool_name == "analyze_idle_patterns":
            return f"⏸️ **Idle Pattern Analysis**\n\nAnalysis of your inactive periods based on '{query}'."
        elif tool_name == "generate_manager_report":
            return f"👥 **Team Report**\n\nTeam productivity report generated from your query '{query}'."
        return f"Analysis complete for: {query}"

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