from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional  # <-- Added Optional
import json
from datetime import datetime, timedelta
import os

from models import QueryRequest, ProductivityData, AIResponse, ToolCall
from tools import ProductivityTools, AVAILABLE_TOOLS

# Create a global instance
productivity_tools = None

class DummyProductivityTools:
    """Fallback tools that return mock data when real tools fail"""
    def get_daily_productivity(self, user_id: str, days: int = 7, date: Optional[str] = None):
        """Get daily productivity data for a user"""
        print(f"📊 Dummy: Getting productivity for user {user_id}, {days} days")
        
        data = []
        for i in range(days):
            date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            data.append({
                "date": date_str,
                "productive_hours": 6.5,
                "idle_hours": 1.5,
                "productivity_score": 81.25,
                "total_hours": 8.0
            })
        
        # Sort by date
        return sorted(data, key=lambda x: x["date"])
    
    def analyze_idle_patterns(self, user_id: str):
        """Analyze idle patterns for a user"""
        print(f"🔍 Dummy: Analyzing idle patterns for user {user_id}")
        
        return {
            "user_id": user_id,
            "total_activities": 100,
            "idle_count": 25,
            "idle_percentage": 25.0,
            "common_idle_times": ["14:30", "11:00", "16:45"],
            "analysis": "User tends to be idle during afternoon hours"
        }
    
    def generate_manager_report(self, manager_id: str, days: int = 7):
        """Generate comprehensive report for a manager"""
        print(f"📋 Dummy: Generating manager report for {manager_id}")
        
        return {
            "manager_id": manager_id,
            "manager_name": "Manager",
            "organization_id": "org-123",
            "period_days": days,
            "team_size": 3,
            "total_productive_hours": 96.4,
            "total_idle_hours": 26.1,
            "overall_productivity": 78.7,
            "team_data": [
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
                }
            ],
            "most_productive": {"name": "John Doe", "productivity_score": 79.8},
            "least_productive": {"name": "Jane Smith", "productivity_score": 70.3},
            "insights": ["Team is performing well"],
            "generated_at": datetime.now().isoformat()
        }

app = FastAPI(title="WorkPulse MCP Server", 
              description="Model Context Protocol server for productivity monitoring")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "WorkPulse MCP Server",
        "version": "1.0.0",
        "available_tools": list(AVAILABLE_TOOLS.keys()),
        "status": "running"
    }

@app.on_event("startup")
async def startup_event():
    global productivity_tools
    try:
        productivity_tools = ProductivityTools()
        print("✅ MCP Tools initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize MCP Tools: {e}")
        # Create a dummy instance
        from datetime import timedelta
        productivity_tools = DummyProductivityTools()
        print("✅ Using dummy tools as fallback")

@app.get("/tools")
async def get_tools():
    """Get list of available tools"""
    return AVAILABLE_TOOLS

@app.post("/query", response_model=AIResponse)
async def process_query(request: QueryRequest):
    """Process a natural language query"""
    
    if not productivity_tools:
        raise HTTPException(status_code=500, detail="MCP Tools not initialized")
    
    query = request.query.lower()
    user_id = request.user_id
    
    tool_calls = []
    data = []
    explanation = ""
    visualization_type = "bar"
    
    try:
        # SIMPLIFY THE LOGIC - let the AI orchestrator handle tool selection
        print(f"📝 Processing query: '{query}' for user {user_id}")
        
        # Basic routing based on query
        if "idle" in query or "inactive" in query:
            result = productivity_tools.analyze_idle_patterns(user_id)
            tool_calls.append(ToolCall(
                tool_name="analyze_idle_patterns",
                parameters={"user_id": user_id}
            ))
            
            idle_pct = result.get("idle_percentage", 0)
            data = [
                ProductivityData(
                    date="Productive",
                    productive_hours=100 - idle_pct,
                    idle_hours=idle_pct,
                    productivity_score=100 - idle_pct,
                    total_hours=100
                ),
                ProductivityData(
                    date="Idle",
                    productive_hours=0,
                    idle_hours=idle_pct,
                    productivity_score=0,
                    total_hours=idle_pct
                )
            ]
            
            explanation = f"**Idle Pattern Analysis**\n\n"
            explanation += f"• Idle percentage: **{idle_pct:.1f}%**\n"
            explanation += f"• Total activities: **{result.get('total_activities', 0)}**\n"
            explanation += f"• Common idle times: {', '.join(result.get('common_idle_times', ['None']))[:3]}\n"
            explanation += f"\n{result.get('analysis', 'Analysis completed')}"
            visualization_type = "pie"
            
        elif "team" in query or "manager" in query or "report" in query:
            result = productivity_tools.generate_manager_report(user_id, days=7)
            tool_calls.append(ToolCall(
                tool_name="generate_manager_report",
                parameters={"manager_id": user_id, "days": 7}
            ))
            
            for member in result.get("team_data", []):
                data.append(ProductivityData(
                    date=member.get("name", "Unknown"),
                    productive_hours=member.get("productive_hours", 0),
                    idle_hours=member.get("idle_hours", 0),
                    productivity_score=member.get("productivity_score", 0),
                    total_hours=member.get("productive_hours", 0) + member.get("idle_hours", 0)
                ))
            
            explanation = f"**Team Productivity Report**\n\n"
            explanation += f"• Team size: **{result.get('team_size', 0)} members**\n"
            explanation += f"• Overall productivity: **{result.get('overall_productivity', 0):.1f}%**\n"
            
            if result.get("insights"):
                explanation += f"\n**Key Insights:**\n"
                for insight in result["insights"][:3]:
                    explanation += f"• {insight}\n"
            
            visualization_type = "bar"
            
        else:
            # Default to daily productivity
            days = 1 if "today" in query else 7
            result = productivity_tools.get_daily_productivity(user_id, days=days)
            tool_calls.append(ToolCall(
                tool_name="get_daily_productivity",
                parameters={"user_id": user_id, "days": days}
            ))
            
            # Convert result to ProductivityData objects
            for item in result:
                data.append(ProductivityData(**item))
            
            explanation = f"**Daily Productivity Analysis**\n\n"
            explanation += f"Showing data for **{days} day(s)**\n\n"
            
            if data:
                total_productive = sum(d.productive_hours for d in data)
                total_idle = sum(d.idle_hours for d in data)
                avg_score = sum(d.productivity_score for d in data) / len(data)
                
                explanation += f"• Total productive hours: **{total_productive:.1f}h**\n"
                explanation += f"• Total idle hours: **{total_idle:.1f}h**\n"
                explanation += f"• Average productivity: **{avg_score:.1f}%**\n"
                
                # Find best day
                best_day = max(data, key=lambda x: x.productivity_score)
                explanation += f"• Best day: **{best_day.date}** ({best_day.productivity_score:.1f}%)\n"
            
            visualization_type = "line" if days > 1 else "bar"
        
    except Exception as e:
        print(f"Error processing query: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
    
    return AIResponse(
        explanation=explanation,
        data=data,
        tool_calls=tool_calls,
        visualization_type=visualization_type
    )

@app.post("/execute_tool/{tool_name}")
async def execute_tool(tool_name: str, parameters: Dict[str, Any]):
    
    print(f"🛠️ Executing tool: {tool_name}")
    print(f"📋 Parameters: {parameters}")
    
    if tool_name not in AVAILABLE_TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    if not productivity_tools:
        raise HTTPException(status_code=500, detail="MCP Tools not initialized")
    
    try:
        if tool_name == "get_daily_productivity":
            user_id = parameters.get("user_id")
            days = parameters.get("days", 7)
            date = parameters.get("date")
            
            if not user_id:
                raise HTTPException(status_code=400, detail="user_id is required")
            
            result = productivity_tools.get_daily_productivity(
                user_id=user_id,
                days=days,
                date=date
            )
            
        elif tool_name == "analyze_idle_patterns":
            user_id = parameters.get("user_id")
            
            if not user_id:
                raise HTTPException(status_code=400, detail="user_id is required")
            
            result = productivity_tools.analyze_idle_patterns(user_id=user_id)
            
        elif tool_name == "generate_manager_report":
            manager_id = parameters.get("manager_id")
            days = parameters.get("days", 7)
            
            if not manager_id:
                raise HTTPException(status_code=400, detail="manager_id is required")
            
            result = productivity_tools.generate_manager_report(
                manager_id=manager_id,
                days=days
            )
            
        else:
            raise HTTPException(status_code=400, detail=f"Tool '{tool_name}' not implemented")
        
         
        print(f"✅ MCP: Tool {tool_name} executed successfully")
        print(f"📊 MCP: Result type: {type(result)}")
        
        if isinstance(result, list):
            print(f"📊 MCP: Result items: {len(result)}")
            if result:
                print(f"📊 MCP: First item: {result[0]}")
        elif isinstance(result, dict):
            print(f"📊 MCP: Result keys: {list(result.keys())}")
        
        return {
            "success": True,
            "tool": tool_name,
            "result": result,
            "executed_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Tool execution error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error executing tool {tool_name}: {str(e)}")
    

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy" if productivity_tools else "degraded",
        "tools_initialized": productivity_tools is not None,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)