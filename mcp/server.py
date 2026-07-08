from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional, List
import json
from datetime import datetime, timedelta, timezone
from models import QueryRequest, ProductivityData, AIResponse, ToolCall
from tools import ProductivityTools, AVAILABLE_TOOLS
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="WorkPulse MCP Server", 
              description="Model Context Protocol server for productivity monitoring")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instance
productivity_tools = None

@app.on_event("startup")
async def startup_event():
    global productivity_tools
    try:
        productivity_tools = ProductivityTools()
        print("✅ MCP Tools initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize MCP Tools: {e}")
        productivity_tools = None

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "WorkPulse MCP Server",
        "version": "1.0.0",
        "available_tools": list(AVAILABLE_TOOLS.keys()),
        "status": "running"
    }

@app.get("/tools")
async def get_tools():
    """Get list of available tools"""
    return AVAILABLE_TOOLS

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
            
            if not user_id:
                raise HTTPException(status_code=400, detail="user_id is required")
            
            result = productivity_tools.get_daily_productivity(
                user_id=user_id,
                days=days
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
        
        elif tool_name == "get_team_productivity":
            manager_id = parameters.get("manager_id")
            days = parameters.get("days", 7)
            
            if not manager_id:
                raise HTTPException(status_code=400, detail="manager_id is required")
            
            result = productivity_tools.get_team_productivity(
                manager_id=manager_id,
                days=days
            )
            
        elif tool_name == "get_team_idle_analysis":
            manager_id = parameters.get("manager_id")
            days = parameters.get("days", 30)
            
            if not manager_id:
                raise HTTPException(status_code=400, detail="manager_id is required")
            
            result = productivity_tools.get_team_idle_analysis(
                manager_id=manager_id,
                days=days
            )
            
        else:
            raise HTTPException(status_code=400, detail=f"Tool '{tool_name}' not implemented")
        
        print(f"✅ MCP: Tool {tool_name} executed successfully")
        
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