from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

# Request/Response models
class QueryRequest(BaseModel):
    user_id: str
    query: str
    date_range: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class ProductivityData(BaseModel):
    date: str
    productive_hours: float
    idle_hours: float
    productivity_score: float
    total_hours: float

class ToolCall(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]

class AIResponse(BaseModel):
    explanation: str
    data: List[ProductivityData]
    tool_calls: List[ToolCall]
    visualization_type: str  # "bar", "line", "pie", "table"