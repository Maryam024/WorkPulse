import secrets
from datetime import datetime, timezone, timedelta
from supabase_client import supabase
from email_service import email_sender

class PasswordRecovery:
    def __init__(self):
        self.reset_tokens = {}  # In production, use Redis or database
    
    def generate_reset_token(self, user_id: str) -> str:
        """Generate a password reset token"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Store token in database
        supabase.table("password_reset_tokens").insert({
            "user_id": user_id,
            "token": token,
            "expires_at": expires_at.isoformat(),
            "used": False
        }).execute()
        
        return token
    
    def send_reset_email(self, email: str, token: str):
        """Send password reset email"""
        reset_url = f"http://localhost:5000/reset-password/{token}"
        
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                       color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h2>Reset Your WorkPulse Password</h2>
            </div>
            
            <div style="padding: 30px; background: #f9f9f9;">
                <p>You requested to reset your WorkPulse password.</p>
                
                <div style="background: white; border-radius: 10px; padding: 20px; margin: 20px 0; 
                           box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center;">
                    <a href="{reset_url}" 
                       style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                              color: white; padding: 15px 30px; border-radius: 50px; 
                              text-decoration: none; font-weight: bold; display: inline-block;">
                        Reset Password
                    </a>
                </div>
                
                <p>Or copy and paste this link in your browser:</p>
                <p style="word-break: break-all; color: #667eea; font-size: 14px;">
                    {reset_url}
                </p>
                
                <div style="background: #fff3cd; color: #856404; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <strong>⚠️ Important:</strong>
                    <ul style="margin: 10px 0 0 0; padding-left: 20px;">
                        <li>This link expires in 1 hour</li>
                        <li>If you didn't request this, please ignore this email</li>
                        <li>For security, don't share this link with anyone</li>
                    </ul>
                </div>
                
                <p style="margin-top: 30px;">Best regards,<br>
                <strong>The WorkPulse Team</strong></p>
            </div>
        </div>
        """
        
        return email_sender.send(
            to_email=email,
            subject="Reset Your WorkPulse Password",
            html=html,
            from_email="WorkPulse <onboarding@resend.dev>"
        )
    
    def validate_token(self, token: str) -> dict:
        """Validate reset token and return user info if valid"""
        try:
            # First, get the token data
            response = supabase.table("password_reset_tokens").select("*").eq("token", token).eq("used", False).execute()
            
            if not response.data:
                return {"valid": False, "error": "Invalid or expired token"}
            
            token_data = response.data[0]
            expires_at = datetime.fromisoformat(token_data["expires_at"].replace('Z', '+00:00'))
            
            if expires_at < datetime.now(timezone.utc):
                return {"valid": False, "error": "Token has expired"}
            
            # Then, get user info separately
            user_response = supabase.table("profiles").select("email, name").eq("id", token_data["user_id"]).execute()
            
            if not user_response.data:
                return {"valid": False, "error": "User not found"}
            
            user_info = user_response.data[0]
            
            return {
                "valid": True,
                "user_id": token_data["user_id"],
                "user_email": user_info["email"],
                "user_name": user_info["name"]
            }
        except Exception as e:
            print(f"❌ Token validation error: {e}")
            return {"valid": False, "error": str(e)}
    
    def mark_token_used(self, token: str):
        """Mark a reset token as used"""
        supabase.table("password_reset_tokens").update({
            "used": True,
            "used_at": datetime.now(timezone.utc).isoformat()
        }).eq("token", token).execute()

# Global instance
password_recovery = PasswordRecovery()