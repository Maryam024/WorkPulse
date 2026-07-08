# team_resolver.py - SIMPLIFIED VERSION
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

class TeamDataResolver:
    """Centralized resolver for team data"""
    
    @staticmethod
    def get_supabase_client():
        """Get Supabase client"""
        supabase_url = os.getenv("SUPABASE_URL")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not service_role_key:
            raise ValueError("Missing Supabase credentials")
        
        return create_client(supabase_url, service_role_key)
    
    @staticmethod
    def get_team_members(manager_app_id: str, include_inactive: bool = True) -> List[Dict[str, Any]]:
        """Get team members for a manager"""
        try:
            supabase = TeamDataResolver.get_supabase_client()
            
            # First, find the manager's database ID
            # Try to find by custom_id or email
            manager_response = supabase.table("profiles").select(
                "id, name, email, custom_id"
            ).or_(f"custom_id.eq.{manager_app_id},email.ilike.%{manager_app_id}%").execute()
            
            if not manager_response.data:
                return []
            
            manager_db_id = manager_response.data[0]["id"]
            
            # Get team members
            query = supabase.table("profiles").select(
                "id, name, email, role, is_active, manager_id, created_at"
            ).eq("manager_id", manager_db_id)
            
            if not include_inactive:
                query = query.eq("is_active", True)
                
            response = query.execute()
            
            members = response.data or []
            
            # Format members
            for member in members:
                member.setdefault("name", "Unknown")
                member.setdefault("email", "")
                member.setdefault("is_active", True)
                member.setdefault("role", "user")
                
            return sorted(members, key=lambda x: x.get("name", ""))
            
        except Exception as e:
            print(f"❌ Error fetching team members: {e}")
            return []