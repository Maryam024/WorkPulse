# email_service.py
import os
import requests
from typing import Optional
import resend

class EmailSender:
    def __init__(self):
        self.resend_key = os.getenv('RESEND_API_KEY')
        self.sendgrid_key = os.getenv('SENDGRID_API_KEY')
    
    def send(self, to_email: str, subject: str, html: str, from_email: Optional[str] = None) -> bool:
        """Send email using available service"""
        
        # Try Resend first
        if self.resend_key:
            return self._send_resend(to_email, subject, html, from_email)
        
        # Fallback to SendGrid
        elif self.sendgrid_key:
            return self._send_sendgrid(to_email, subject, html, from_email)
        
        # No email service configured
        else:
            print(f"📧 Email would be sent to {to_email}: {subject}")
            print(f"   HTML: {html[:100]}...")
            return False
    
    def _send_resend(self, to_email, subject, html, from_email):
        """Send via Resend API"""
       
        
        resend.api_key = self.resend_key
        
        params = {
            "from": from_email or "WorkPulse <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        
        try:
            resend.Emails.send(params)
            print(f"✅ Email sent to {to_email} via Resend")
            return True
        except Exception as e:
            print(f"❌ Resend error: {e}")
            return False
    
    def _send_sendgrid(self, to_email, subject, html, from_email):
        """Send via SendGrid API"""
        url = "https://api.sendgrid.com/v3/mail/send"
        
        headers = {
            "Authorization": f"Bearer {self.sendgrid_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email or "onboarding@resend.dev", "name": "WorkPulse"},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 202:
                print(f"✅ Email sent to {to_email} via SendGrid")
                return True
            else:
                print(f"❌ SendGrid error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ SendGrid error: {e}")
            return False
   
    
    # Add this method to EmailSender class for weekly reports
    def send_weekly_report(self, manager_email, report_data, manager_name="Manager"):
        """Send weekly productivity report"""
        
        # Format team data into HTML table
        team_rows = ""
        for member in report_data['team']:
            team_rows += f"""
            <tr>
                <td>{member['name']}</td>
                <td>{member['productive_hours']:.1f}h</td>
                <td>{member['idle_hours']:.1f}h</td>
                <td><strong>{member['productivity_score']:.1f}%</strong></td>
            </tr>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; }}
                .stats-card {{ background: white; border-radius: 10px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th {{ background: #f8f9fa; padding: 12px; text-align: left; }}
                td {{ padding: 12px; border-bottom: 1px solid #dee2e6; }}
                .highlight {{ color: #28a745; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 WorkPulse Weekly Report</h1>
                    <p>Period: {report_data['period']}</p>
                </div>
                
                <div class="content">
                    <div class="stats-card">
                        <h3>Hello {manager_name},</h3>
                        <p>Here's your team's productivity report for the past week:</p>
                        
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin: 30px 0;">
                            <div style="background: #e7f5ff; padding: 20px; border-radius: 10px;">
                                <h4 style="color: #0056b3; margin-top: 0;">📈 Total Productive Hours</h4>
                                <p style="font-size: 32px; font-weight: bold; color: #0056b3; margin: 10px 0;">{report_data['total_productive']:.1f}h</p>
                            </div>
                            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px;">
                                <h4 style="color: #28a745; margin-top: 0;">🏆 Average Productivity</h4>
                                <p style="font-size: 32px; font-weight: bold; color: #28a745; margin: 10px 0;">{report_data['avg_productivity']:.1f}%</p>
                            </div>
                        </div>
                        
                        <div style="background: #fff3cd; padding: 20px; border-radius: 10px; margin: 20px 0;">
                            <h4 style="color: #856404; margin-top: 0;">👑 Most Productive Team Member</h4>
                            <p style="font-size: 24px; font-weight: bold; color: #856404; margin: 10px 0;">{report_data['most_productive']}</p>
                        </div>
                    </div>
                    
                    <div class="stats-card">
                        <h3>Team Performance Details</h3>
                        <table>
                            <thead>
                                <tr>
                                    <th>Team Member</th>
                                    <th>Productive Hours</th>
                                    <th>Idle Hours</th>
                                    <th>Productivity Score</th>
                                </tr>
                            </thead>
                            <tbody>
                                {team_rows}
                            </tbody>
                        </table>
                    </div>
                    
                    <p style="color: #6c757d; font-size: 14px; margin-top: 30px;">
                        <i>This report was automatically generated by WorkPulse.<br>
                        You can view detailed analytics in your dashboard at any time.</i>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send(
            to_email=manager_email,
            subject=f"WorkPulse Weekly Report - {report_data['period']}",
            html=html,
            from_email="WorkPulse <onboarding@resend.dev>"
        )
    # Add this method to EmailSender class
    def send_user_credentials_to_manager(self, manager_email, user_name, user_email, temp_password, manager_name):
        """Send user credentials to manager"""
        
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h2>New Team Member Credentials</h2>
            </div>
            
            <div style="padding: 30px; background: #f9f9f9;">
                <p>Hello <strong>{manager_name}</strong>,</p>
                
                <p>You have successfully added <strong>{user_name}</strong> to your WorkPulse organization.</p>
                
                <div style="background: white; border-radius: 10px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <h3 style="color: #333; margin-top: 0;">Share these credentials with {user_name}</h3>
                    <table style="width: 100%;">
                        <tr>
                            <td style="padding: 10px; font-weight: bold;">Login URL:</td>
                            <td style="padding: 10px;">
                                <a href="http://localhost:5000/login">http://localhost:5000/login</a>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; font-weight: bold;">Email:</td>
                            <td style="padding: 10px;">{user_email}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; font-weight: bold;">Temporary Password:</td>
                            <td style="padding: 10px; color: #dc3545; font-family: monospace; font-size: 18px; font-weight: bold;">
                                {temp_password}
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div style="background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <strong>⚠️ Important Security Note:</strong>
                    <ul style="margin: 10px 0 0 0; padding-left: 20px;">
                        <li>Share these credentials securely with {user_name}</li>
                        <li>User will be prompted to set a new password on first login</li>
                        <li>Do not share this email with anyone else</li>
                    </ul>
                </div>
                
                <p>Best regards,<br>
                <strong>The WorkPulse Team</strong></p>
            </div>
        </div>
        """
        
        return self.send(
            to_email=manager_email,
            subject=f"WorkPulse - Credentials for {user_name}",
            html=html,
            from_email="WorkPulse <onboarding@resend.dev>"
        )
    
# Global email sender instance
email_sender = EmailSender()