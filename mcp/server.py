from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import json
from datetime import datetime
import os

from models import QueryRequest, ProductivityData, AIResponse, ToolCall
from tools import ProductivityTools, AVAILABLE_TOOLS

# Create a global instance
productivity_tools = None

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
        "available_tools": list(AVAILABLE_TOOLS.keys())
    }
@app.on_event("startup")
async def startup_event():
    global productivity_tools
    try:
        productivity_tools = ProductivityTools()
        print("✅ MCP Tools initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize MCP Tools: {e}")
        productivity_tools = None
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
        if "idle" in query or "inactive" in query:
            # Use the tools instance
            result = productivity_tools.analyze_idle_patterns(user_id)
            tool_calls.append(ToolCall(
                tool_name="analyze_idle_patterns",
                parameters={"user_id": user_id}
            ))
            
            # Format real data for visualization
            idle_pct = result.get("idle_percentage", 0)
            data = [
                {
                    "date": "Productive",
                    "productive_hours": 100 - idle_pct,
                    "idle_hours": idle_pct,
                    "productivity_score": 100 - idle_pct,
                    "total_hours": 100
                },
                {
                    "date": "Idle", 
                    "productive_hours": 0,
                    "idle_hours": idle_pct,
                    "productivity_score": 0,
                    "total_hours": idle_pct
                }
            ]
            
            explanation = f"**Idle Pattern Analysis**\n\n"
            explanation += f"• Idle percentage: **{idle_pct:.1f}%**\n"
            explanation += f"• Total activities analyzed: **{result.get('total_activities', 0)}**\n"
            explanation += f"• Idle count: **{result.get('idle_count', 0)}**\n"
            
            if result.get('common_idle_times'):
                explanation += f"• Common idle times: {', '.join(result['common_idle_times'][:3])}\n"
            
            explanation += f"\n**Analysis:** {result.get('analysis', 'No analysis available')}"
            visualization_type = "pie"
            
        elif "team" in query or "manager" in query or "report" in query:
            # Generate manager report
            result = productivity_tools.generate_manager_report(user_id, days=7)
            tool_calls.append(ToolCall(
                tool_name="generate_manager_report",
                parameters={"manager_id": user_id, "days": 7}
            ))
            
            # Format real team data
            team_data = result.get("team_data", [])
            for member in team_data:
                data.append({
                    "date": member.get("name", "Unknown"),
                    "productive_hours": member.get("productive_hours", 0),
                    "idle_hours": member.get("idle_hours", 0),
                    "productivity_score": member.get("productivity_score", 0),
                    "total_hours": member.get("productive_hours", 0) + member.get("idle_hours", 0)
                })
            
            explanation = f"**Team Productivity Report**\n\n"
            explanation += f"• Team size: **{result.get('team_size', 0)} members**\n"
            explanation += f"• Overall productivity: **{result.get('overall_productivity', 0):.1f}%**\n"
            explanation += f"• Total productive hours: **{result.get('total_productive_hours', 0):.1f}h**\n"
            explanation += f"• Total idle hours: **{result.get('total_idle_hours', 0):.1f}h**\n"
            
            if result.get("most_productive"):
                explanation += f"• Top performer: **{result['most_productive'].get('name', 'Unknown')}** ({result['most_productive'].get('productivity_score', 0):.1f}%)\n"
            
            if result.get("insights"):
                explanation += f"\n**Key Insights:**\n"
                for insight in result["insights"][:3]:
                    explanation += f"• {insight}\n"
            
            visualization_type = "bar"
            
        else:
            # Default to daily productivity
            days = 1 if "today" in query else 7
            data = productivity_tools.get_daily_productivity(user_id, days=days)
            tool_calls.append(ToolCall(
                tool_name="get_daily_productivity",
                parameters={"user_id": user_id, "days": days}
            ))
            
            explanation = f"**Daily Productivity Analysis**\n\n"
            explanation += f"Showing data for **{days} day(s)**\n\n"
            
            if data:
                total_productive = sum(d.get("productive_hours", 0) for d in data)
                total_idle = sum(d.get("idle_hours", 0) for d in data)
                avg_score = sum(d.get("productivity_score", 0) for d in data) / len(data)
                
                explanation += f"• Total productive hours: **{total_productive:.1f}h**\n"
                explanation += f"• Total idle hours: **{total_idle:.1f}h**\n"
                explanation += f"• Average productivity: **{avg_score:.1f}%**\n"
                
                # Find best day
                best_day = max(data, key=lambda x: x.get("productivity_score", 0))
                explanation += f"• Best day: **{best_day.get('date', 'Unknown')}** ({best_day.get('productivity_score', 0):.1f}%)\n"
            
            visualization_type = "line" if days > 1 else "bar"
        
    except Exception as e:
        print(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
    
    # Convert data to ProductivityData models
    productivity_data = [
        ProductivityData(**item) for item in data
    ]
    
    return AIResponse(
        explanation=explanation,
        data=productivity_data,
        tool_calls=tool_calls,
        visualization_type=visualization_type
    )
@app.post("/execute_tool/{tool_name}")
async def execute_tool(tool_name: str, parameters: Dict[str, Any]):
    """Execute a specific tool with parameters"""
    
    if tool_name not in AVAILABLE_TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    try:
        # Create instance here
        tools = ProductivityTools()
        
        if tool_name == "get_daily_productivity":
            result = tools.get_daily_productivity(
                user_id=parameters.get("user_id"),
                days=parameters.get("days", 7)
            )
            
        elif tool_name == "analyze_idle_patterns":
            result = tools.analyze_idle_patterns(
                user_id=parameters.get("user_id")
            )
            
        elif tool_name == "generate_manager_report":
            result = tools.generate_manager_report(
                manager_id=parameters.get("manager_id"),
                days=parameters.get("days", 7)
            )
            
        else:
            raise HTTPException(status_code=400, detail=f"Tool '{tool_name}' not implemented")
        
        return {
            "success": True,
            "tool": tool_name,
            "result": result,
            "executed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing tool: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)