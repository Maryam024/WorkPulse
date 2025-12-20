# frontend/app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta, timezone
import pandas as pd
import hashlib
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
# Add after other imports
from email_service import email_sender
import schedule
import time
import json
import requests
from datetime import datetime

# Import AI orchestrator with error handling
try:
    from ai_orchestrator import AIOrchestrator
except ImportError as e:
    print(f"AI orchestrator import error: {e}")
    AIOrchestrator = None  # Set the class to None instead

# Later initialize properly
ai_orchestrator = None  # Global variable

def initialize_ai():
    """Initialize AI orchestrator"""
    global ai_orchestrator
    if AIOrchestrator is None:
        print("❌ AI Orchestrator module not available")
        return False
    
    try:
        ai_orchestrator = AIOrchestrator()
        print("✅ AI Orchestrator initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize AI: {e}")
        ai_orchestrator = None
        return False

# Initialize AI when app starts
initialize_ai()
# Load environment variables FIRST
load_dotenv()

# Import create_client from supabase
from supabase import create_client

# Then import supabase
try:
    from supabase_client import supabase
    print("Supabase client imported successfully")
except ImportError as e:
    print(f"Supabase import error: {e}")
    exit(1)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'workpulse-secret-key-2024')

# -----------------------
# Auth & Helper Functions
# -----------------------
def generate_temp_password():
    """Generate a temporary password for new users"""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(10))

def require_login(required_role=None):
    if 'access_token' not in session:
        print("No access token in session")
        return False
    
    try:
        user_response = supabase.auth.get_user(session['access_token'])
        
        if not user_response.user:
            print("Invalid access token")
            session.clear()
            return False
        
        if required_role and session.get('role') != required_role:
            print(f"Role mismatch: required {required_role}, has {session.get('role')}")
            return False
            
        return True
        
    except Exception as e:
        print(f"Auth check error: {e}")
        session.clear()
        return False

def get_user_settings(user_id):
    """Get user settings including theme preference"""
    try:
        response = supabase.table("user_settings").select("*").eq("user_id", user_id).execute()
        if response.data:
            return response.data[0]
        else:
            # Create default settings
            default_settings = {
                "user_id": user_id,
                "theme": "light",
                "email_notifications": True
            }
            supabase.table("user_settings").insert(default_settings).execute()
            return default_settings
    except Exception as e:
        print(f"Error getting user settings: {e}")
        return {"theme": "light", "email_notifications": True}

def update_user_theme(user_id, theme):
    """Update user's theme preference"""
    try:
        supabase.table("user_settings").upsert({
            "user_id": user_id,
            "theme": theme,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return True
    except Exception as e:
        print(f"Error updating theme: {e}")
        return False

def calculate_productivity_stats(activity_data):
    """
    Calculate productive and idle hours from activity logs.
    Activity logs should contain:
    - "User became idle" events (start of idle period)
    - "User became active" events (end of idle period)
    - "Heartbeat" events (for online status)
    - "User activity" events (for active periods)
    """
    if not activity_data:
        return {
            "productive_hours": 0,
            "idle_hours": 0,
            "productivity_score": 0
        }
    
    # Sort by timestamp
    activity_data = sorted(activity_data, key=lambda x: x["timestamp"])
    
    total_idle_seconds = 0
    total_active_seconds = 0
    current_state = "active"  # Assume starting as active
    last_timestamp = None
    
    print(f"📊 Processing {len(activity_data)} activity records...")
    
    for i, entry in enumerate(activity_data):
        try:
            ts = datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))
            event = entry["event"]
            
            if last_timestamp is None:
                last_timestamp = ts
                # Determine initial state
                if event in ["User became idle", "Heartbeat"]:
                    current_state = "idle"
                else:
                    current_state = "active"
                continue
            
            # Calculate time difference in seconds
            delta_seconds = (ts - last_timestamp).total_seconds()
            
            if delta_seconds > 0:
                if current_state == "active":
                    total_active_seconds += delta_seconds
                else:
                    total_idle_seconds += delta_seconds
            
            # Update state based on event
            if event == "User became idle":
                current_state = "idle"
            elif event == "User became active":
                current_state = "active"
            
            last_timestamp = ts
            
        except Exception as e:
            print(f"⚠️ Error processing activity record {i}: {e}")
            continue
    
    # Convert seconds to hours
    total_active_hours = total_active_seconds / 3600
    total_idle_hours = total_idle_seconds / 3600
    
    # Calculate productivity score
    work_hours = total_active_hours + total_idle_hours
    if work_hours > 0:
        productivity_score = (total_active_hours / work_hours) * 100
    else:
        productivity_score = 0
    
    print(f"📈 Stats: Active={total_active_hours:.2f}h, Idle={total_idle_hours:.2f}h, Score={productivity_score:.1f}%")
    
    return {
        "productive_hours": round(total_active_hours, 2),
        "idle_hours": round(total_idle_hours, 2),
        "productivity_score": round(productivity_score, 1)
    }
def get_user_activity_data(user_id=None, days=7):
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    query = supabase.table("user_activity").select("*")
    if user_id:
        query = query.eq("user_id", user_id)
    
    resp = query.gte("timestamp", start_date.isoformat()).order("timestamp", desc=True).execute()
    return resp.data or []

# -----------------------
# Auth Routes (Updated)
# -----------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Manager signup - no service role key needed"""
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        if role != 'manager':
            return render_template('signup.html', error="Only manager accounts can be created directly")
        
        print(f"Attempting manager signup: {email}")
        
        try:
            # STEP 1: Try to sign up normally
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "name": name,
                        "role": "manager"
                    }
                }
            })
            
            if not auth_response.user:
                return render_template('signup.html', error="Signup failed - auth error")
            
            user_id = auth_response.user.id
            print(f"User created with ID: {user_id}")
            
            # STEP 2: Create organization
            org_response = supabase.table("organizations").insert({
                "name": f"{name}'s Organization",
                "created_at": datetime.now(timezone.utc).isoformat()
            }).execute()
            
            if not org_response.data:
                return render_template('signup.html', error="Failed to create organization")
            
            org_id = org_response.data[0]['id']
            
            # STEP 3: Create manager profile
            profile_data = {
                "id": user_id,
                "name": name,
                "role": role,
                "email": email,
                "organization_id": org_id,
                "manager_id": None,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            profile_response = supabase.table("profiles").insert(profile_data).execute()
            
            if not profile_response.data:
                supabase.table("organizations").delete().eq("id", org_id).execute()
                return render_template('signup.html', error="Failed to create profile")
            
            # STEP 4: Update organization with manager_id
            supabase.table("organizations").update({
                "manager_id": user_id,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", org_id).execute()
            
            # STEP 5: Create user settings
            supabase.table("user_settings").insert({
                "user_id": user_id,
                "theme": "light",
                "email_notifications": True
            }).execute()
            
            # STEP 6: Send welcome email in background
            try:
                threading.Thread(
                    target=send_welcome_email_to_manager,
                    args=(email, name)
                ).start()
            except Exception as email_error:
                print(f"Email sending failed (non-critical): {email_error}")
            
            # STEP 7: Show success message and redirect to login
            return render_template('signup.html', 
                success_message="✅ Account created successfully! You can now login with your credentials.")
                
        except Exception as e:
            error_msg = str(e).lower()
            print(f"Signup error details: {e}")
            
            if "user already registered" in error_msg:
                return render_template('signup.html', error="Email already registered. Please login instead.")
            elif "email already taken" in error_msg:
                return render_template('signup.html', error="Email already registered. Please login instead.")
            elif "failed to fetch" in error_msg:
                return render_template('signup.html', error="Network error. Please check your internet connection.")
            else:
                return render_template('signup.html', error=f"Signup error: {str(e)}")
    
    return render_template('signup.html')

def send_welcome_email_to_manager(manager_email, manager_name):
    """Send welcome email to newly registered manager"""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1>🎉 Welcome to WorkPulse!</h1>
        </div>
        
        <div style="padding: 30px; background: #f9f9f9;">
            <p>Hello <strong>{manager_name}</strong>,</p>
            
            <p>Your WorkPulse manager account has been successfully created!</p>
            
            <div style="background: white; border-radius: 10px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h3 style="color: #333; margin-top: 0;">Your Account Details</h3>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 10px; font-weight: bold;">Login URL:</td>
                        <td style="padding: 10px;">
                            <a href="http://localhost:5000/login">http://localhost:5000/login</a>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; font-weight: bold;">Email:</td>
                        <td style="padding: 10px;">{manager_email}</td>
                    </tr>
                </table>
            </div>
            
            <div style="background: #e7f5ff; color: #0056b3; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <strong>💡 Tip:</strong> You can now add team members and track their productivity from your dashboard.
            </div>
            
            <p>You now have access to:</p>
            <ul>
                <li>Add team members to your organization</li>
                <li>Track team productivity in real-time</li>
                <li>Receive weekly productivity reports</li>
                <li>Full administrative control over your team</li>
            </ul>
            
            <p style="margin-top: 30px;">Best regards,<br>
            <strong>The WorkPulse Team</strong></p>
        </div>
    </div>
    """
    
    try:
        return email_sender.send(
            to_email=manager_email,
            subject="Welcome to WorkPulse - Your Manager Account is Ready!",
            html=html,
            from_email="WorkPulse <onboarding@resend.dev>"
        )
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            login_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if hasattr(login_response, 'session') and login_response.session:
                session['access_token'] = login_response.session.access_token
                
                # Check if user exists in profiles
                profile_response = supabase.table("profiles").select("*").eq("id", login_response.user.id).execute()
                
                if not profile_response.data:
                    # Try to get user info directly from auth
                    user_info = supabase.auth.get_user(login_response.session.access_token)
                    if user_info.user:
                        # Create a basic profile if doesn't exist
                        try:
                            supabase.table("profiles").insert({
                                "id": user_info.user.id,
                                "name": user_info.user.email.split('@')[0],
                                "role": "user",
                                "email": user_info.user.email,
                                "organization_id": None,
                                "manager_id": None,
                                "is_active": True
                            }).execute()
                            
                            profile = {
                                "id": user_info.user.id,
                                "name": user_info.user.email.split('@')[0],
                                "role": "user",
                                "email": user_info.user.email,
                                "organization_id": None
                            }
                        except:
                            return render_template('login.html', error="Account setup incomplete. Contact your manager.")
                    else:
                        return render_template('login.html', error="Account not found. Please contact your manager.")
                else:
                    profile = profile_response.data[0]
                
                if not profile.get('is_active', True):
                    return render_template('login.html', error="Account is deactivated. Contact your manager.")
                
                session['user'] = {
                    'id': login_response.user.id,
                    'email': login_response.user.email,
                    'name': profile.get('name', 'User'),
                    'organization_id': profile.get('organization_id')
                }
                session['role'] = profile.get('role', 'user')
                
                # Check if password needs to be changed
                if profile.get('temp_password', False):
                    return redirect(url_for('change_password'))
                
                # Redirect based on role
                if session['role'] == 'user':
                    return redirect(url_for('user_dashboard'))
                elif session['role'] == 'manager':
                    return redirect(url_for('manager_dashboard'))
                else:
                    return redirect(url_for('index'))
                    
        except Exception as e:
            error_msg = str(e).lower()
            print(f"Login error: {error_msg}")
            
            if "invalid login credentials" in error_msg:
                return render_template('login.html', error="Invalid email or password")
            else:
                return render_template('login.html', error=f"Login failed. Please try again.")
    
    # Check for password changed notification
    password_changed = request.args.get('password_changed') == 'true'
    
    return render_template('login.html', password_changed=password_changed)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/update-theme', methods=['POST'])
def update_theme():
    if 'access_token' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    theme = data.get('theme')
    
    if theme not in ['light', 'dark']:
        return jsonify({'error': 'Invalid theme'}), 400
    
    user_id = session['user']['id']
    if update_user_theme(user_id, theme):
        session['theme'] = theme
        return jsonify({'success': True, 'theme': theme})
    else:
        return jsonify({'error': 'Failed to update theme'}), 500

# -----------------------
# User Dashboard (Simplified)
# -----------------------
@app.route('/')
def index():
    if 'access_token' in session:
        return redirect(url_for('user_dashboard') if session.get('role') == 'user' else url_for('manager_dashboard'))
    return redirect(url_for('login'))

@app.route('/user/dashboard')
def user_dashboard():
    if not require_login('user'):
        return redirect(url_for('login'))
    
    # Check if user needs to change password
    user_id = session['user']['id']
    try:
        profile_resp = supabase.table("profiles").select("temp_password").eq("id", user_id).execute()
        if profile_resp.data and profile_resp.data[0].get('temp_password', False):
            # Redirect to password change page
            return redirect(url_for('change_password'))
    except Exception as e:
        print(f"Error checking temp_password: {e}")
        # If there's an error, continue to dashboard
    
    today_activities = get_user_activity_data(user_id, days=1)
    today_stats = calculate_productivity_stats(today_activities)
    weekly_activities = get_user_activity_data(user_id, days=7)
    
    settings = get_user_settings(user_id)
    session['theme'] = settings.get('theme', 'light')
    
    return render_template('user_dashboard.html',
                           user=session.get('user'),
                           theme=session.get('theme', 'light'),
                           today_stats=today_stats)
@app.route('/user/api/dashboard')
def user_dashboard_api():
    if not require_login('user'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user']['id']
    today_activities = get_user_activity_data(user_id, days=1)
    today_stats = calculate_productivity_stats(today_activities)
    
    return jsonify({
        'today_stats': today_stats,
        'user': session.get('user')
    })
# -----------------------
# Manager Dashboard with User Management
# -----------------------
@app.route('/manager/dashboard')
def manager_dashboard():
    if not require_login('manager'):
        return redirect(url_for('login'))
    
    manager_id = session['user']['id']
    org_id = session['user'].get('organization_id')
    
    # Get all users in organization
    users_resp = supabase.table("profiles").select("*").eq("organization_id", org_id).execute()
    users = users_resp.data or []
    
    # Get team stats
    team_stats = []
    total_productive = 0
    total_idle = 0
    
    for user in users:
        if user['role'] == 'user':  # Only calculate for regular users
            user_activities = get_user_activity_data(user['id'], days=1)
            user_stats = calculate_productivity_stats(user_activities)
            is_online = len(user_activities) > 0 and (
                datetime.now(timezone.utc) - datetime.fromisoformat(user_activities[0]['timestamp'].replace('Z', '+00:00'))
            ).total_seconds() < 300
            
            team_stats.append({
                'user': user, 
                'stats': user_stats, 
                'is_online': is_online,
                'productivity_score': user_stats['productivity_score']
            })
            
            total_productive += user_stats['productive_hours']
            total_idle += user_stats['idle_hours']
    
    avg_productivity = (total_productive / (total_productive + total_idle) * 100) if (total_productive + total_idle) > 0 else 0
    
    # Get organization details
    org_resp = supabase.table("organizations").select("*").eq("id", org_id).execute()
    organization = org_resp.data[0] if org_resp.data else {}
    
    return render_template('manager_dashboard.html',
                           manager=session.get('user'),
                           team_stats=team_stats,
                           organization=organization,
                           theme=session.get('theme', 'light'),
                           team_metrics={
                               'total_employees': len([u for u in users if u['role'] == 'user']),
                               'active_employees': len([u for u in team_stats if u['is_online']]),
                               'idle_employees': len([u for u in team_stats if not u['is_online']]),
                               'overall_productivity': round(avg_productivity, 1)
                           })

@app.route('/manager/api/add-user', methods=['POST'])
def add_user():
    if not require_login('manager'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    
    if not name or not email:
        return jsonify({'error': 'Name and email are required'}), 400
    
    manager_id = session['user']['id']
    org_id = session['user'].get('organization_id')
    manager_email = session['user']['email']
    manager_name = session['user']['name']
    
    # Generate temporary password
    temp_password = generate_temp_password()
    
    try:
        # Get service role key
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not service_key:
            return jsonify({'error': 'Server configuration error: Missing service role key'}), 500
        
        # Create admin client with service role key
        from supabase import create_client
        admin_client = create_client(os.getenv("SUPABASE_URL"), service_key)
        
        # Create user with admin API
        auth_response = admin_client.auth.admin.create_user({
            "email": email,
            "password": temp_password,
            "email_confirm": True,  # Auto-confirm email
            "user_metadata": {
                "name": name,
                "temp_password": True
            }
        })
        
        if not auth_response.user:
            return jsonify({'error': 'Failed to create user account'}), 500
        
        user_id = auth_response.user.id
        
        # Create user profile
        profile_data = {
            "id": user_id,
            "name": name,
            "role": "user",
            "email": email,
            "organization_id": org_id,
            "manager_id": manager_id,
            "is_active": True,
            "temp_password": True,  # Mark as needs password change
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Insert profile using regular client
        supabase.table("profiles").insert(profile_data).execute()
        
        # Create default settings
        supabase.table("user_settings").insert({
            "user_id": user_id,
            "theme": "light",
            "email_notifications": True
        }).execute()
        
        # Send credentials to manager
        try:
            email_sender.send_user_credentials_to_manager(
                manager_email, name, email, temp_password, manager_name
            )
        except Exception as email_error:
            print(f"Email sending failed: {email_error}")
            # Don't fail the whole operation if email fails
        
        return jsonify({
            'success': True,
            'message': f'User {name} added successfully. Credentials sent to your email.'
        })
            
    except Exception as e:
        error_msg = str(e).lower()
        print(f"Error adding user: {e}")
        
        if "user already registered" in error_msg or "already exists" in error_msg:
            return jsonify({'error': 'Email already registered'}), 400
        elif "invalid service_role key" in error_msg or "jwt" in error_msg:
            return jsonify({'error': 'Server configuration error. Please check your service role key.'}), 500
        else:
            return jsonify({'error': f'Failed to add user: {str(e)}'}), 500
def send_user_credentials(manager_email, user_name, user_email, temp_password, manager_name):
    return email_sender.send_user_credentials_to_manager(
        manager_email, user_name, user_email, temp_password, manager_name
    )


# Add these routes after login route

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """Allow users to change their temporary password"""
    if 'access_token' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user']['id']
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # Check if passwords match
        if new_password != confirm_password:
            return render_template('change_password.html', error="Passwords do not match")
        
        # Check password strength
        if len(new_password) < 8:
            return render_template('change_password.html', error="Password must be at least 8 characters")
        if not any(c.isupper() for c in new_password):
            return render_template('change_password.html', error="Password must contain at least one uppercase letter")
        if not any(c.islower() for c in new_password):
            return render_template('change_password.html', error="Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in new_password):
            return render_template('change_password.html', error="Password must contain at least one number")
        
        try:
            # Get user email from session
            user_email = session['user']['email']
            
            # First try to login with current password to verify
            try:
                supabase.auth.sign_in_with_password({
                    "email": user_email,
                    "password": current_password
                })
            except Exception as e:
                return render_template('change_password.html', error="Current password is incorrect")
            
            # Update password using Supabase auth
            supabase.auth.update_user({
                "password": new_password
            })
            
            # Update profile to mark password as changed
            supabase.table("profiles").update({
                "temp_password": False,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", user_id).execute()
            
            # Clear any existing sessions and redirect to login
            session.clear()
            return redirect(url_for('login') + '?password_changed=true')
            
        except Exception as e:
            print(f"Password change error: {e}")
            return render_template('change_password.html', error="Failed to update password. Please try again.")
    
    # Check if user needs to change password
    try:
        profile_resp = supabase.table("profiles").select("temp_password").eq("id", user_id).execute()
        if profile_resp.data and not profile_resp.data[0].get('temp_password', False):
            # Password already changed, redirect to dashboard
            if session.get('role') == 'user':
                return redirect(url_for('user_dashboard'))
            else:
                return redirect(url_for('manager_dashboard'))
    except:
        pass
    
    return render_template('change_password.html')

@app.route('/manager/api/update-user/<user_id>', methods=['POST'])
def update_user(user_id):
    if not require_login('manager'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    name = data.get('name')
    is_active = data.get('is_active')
    
    try:
        update_data = {}
        if name:
            update_data['name'] = name
        if is_active is not None:
            update_data['is_active'] = is_active
        
        if update_data:
            supabase.table("profiles").update(update_data).eq("id", user_id).execute()
        
        return jsonify({'success': True, 'message': 'User updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/manager/api/delete-user/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    if not require_login('manager'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get user email before deletion for notification
        user_resp = supabase.table("profiles").select("email").eq("id", user_id).execute()
        user_email = user_resp.data[0]['email'] if user_resp.data else None
        
        # Delete from profiles
        supabase.table("profiles").delete().eq("id", user_id).execute()
        
        # Delete user settings
        supabase.table("user_settings").delete().eq("user_id", user_id).execute()
        
        # TODO: Optionally delete from auth users (requires admin)
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/manager/api/search-users', methods=['GET'])
def search_users():
    if not require_login('manager'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    search_term = request.args.get('q', '')
    org_id = session['user'].get('organization_id')
    
    try:
        if search_term:
            response = supabase.table("profiles").select("*").eq("organization_id", org_id).eq("role", "user").ilike("name", f"%{search_term}%").execute()
        else:
            response = supabase.table("profiles").select("*").eq("organization_id", org_id).eq("role", "user").execute()
        
        users = response.data or []
        
        # Add productivity stats for each user
        for user in users:
            user_activities = get_user_activity_data(user['id'], days=1)
            user_stats = calculate_productivity_stats(user_activities)
            user['productivity_score'] = user_stats['productivity_score']
            user['productive_hours'] = user_stats['productive_hours']
            user['idle_hours'] = user_stats['idle_hours']
        
        return jsonify({'users': users})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/manager/api/send-weekly-report', methods=['POST'])
def trigger_weekly_report():
    if not require_login('manager'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    manager_email = session['user']['email']
    org_id = session['user'].get('organization_id')
    
    try:
        # Get all users in organization
        users_resp = supabase.table("profiles").select("*").eq("organization_id", org_id).eq("role", "user").execute()
        users = users_resp.data or []
        
        # Calculate weekly stats for each user
        team_data = []
        total_productive = 0
        
        for user in users:
            weekly_activities = get_user_activity_data(user['id'], days=7)
            weekly_stats = calculate_productivity_stats(weekly_activities)
            
            team_data.append({
                'name': user['name'],
                'productive_hours': weekly_stats['productive_hours'],
                'idle_hours': weekly_stats['idle_hours'],
                'productivity_score': weekly_stats['productivity_score']
            })
            
            total_productive += weekly_stats['productive_hours']
        
        # Find most productive user
        most_productive = max(team_data, key=lambda x: x['productivity_score']) if team_data else {'name': 'N/A'}
        
        # Prepare report data
        report_data = {
            'period': f"{(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}",
            'team': team_data,
            'total_productive': total_productive,
            'avg_productivity': sum(u['productivity_score'] for u in team_data) / len(team_data) if team_data else 0,
            'most_productive': most_productive['name']
        }
        
        # Send report in background
        threading.Thread(
            target=send_weekly_report,
            args=(manager_email, report_data)
        ).start()
        
        return jsonify({
            'success': True,
            'message': 'Weekly report is being generated and will be sent to your email shortly.'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
def send_weekly_report(manager_email, report_data):
    email_sender.send_weekly_report(manager_email, report_data)

def send_scheduled_weekly_reports():
    """Send weekly reports to all managers"""
    print("Checking for weekly reports to send...")
    
    try:
        # Get all managers
        response = supabase.table("profiles").select("*").eq("role", "manager").execute()
        managers = response.data or []
        
        for manager in managers:
            org_id = manager.get('organization_id')
            if not org_id:
                continue
            
            # Get all users in organization
            users_resp = supabase.table("profiles").select("*").eq("organization_id", org_id).eq("role", "user").execute()
            users = users_resp.data or []
            
            # Calculate weekly stats for each user
            team_data = []
            
            for user in users:
                weekly_activities = get_user_activity_data(user['id'], days=7)
                weekly_stats = calculate_productivity_stats(weekly_activities)
                
                team_data.append({
                    'name': user['name'],
                    'productive_hours': weekly_stats['productive_hours'],
                    'idle_hours': weekly_stats['idle_hours'],
                    'productivity_score': weekly_stats['productivity_score']
                })
            
            if team_data:
                # Prepare report data
                report_data = {
                    'period': f"{(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}",
                    'team': team_data,
                    'total_productive': sum(u['productive_hours'] for u in team_data),
                    'avg_productivity': sum(u['productivity_score'] for u in team_data) / len(team_data),
                    'most_productive': max(team_data, key=lambda x: x['productivity_score'])['name'] if team_data else 'N/A'
                }
                
                # Send report
                email_sender.send_weekly_report(manager['email'], report_data)
                print(f"Sent weekly report to {manager['email']}")
    
    except Exception as e:
        print(f"Error sending scheduled reports: {e}")

# Add a background thread for scheduled reports
def start_scheduler():
    """Start the scheduler in a background thread"""
    # Schedule weekly report every Sunday at 9 AM
    schedule.every().sunday.at("09:00").do(send_scheduled_weekly_reports)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

@app.route('/ai-assistant')
def ai_assistant():
    """AI Assistant dashboard"""
    if not require_login():
        return redirect(url_for('login'))
    
    # Get user settings
    user_id = session['user']['id']
    settings = get_user_settings(user_id)
    session['theme'] = settings.get('theme', 'light')
    
    return render_template('ai_query.html',
                           user=session.get('user'),
                           role=session.get('role'),
                           theme=session.get('theme', 'light'))

@app.route('/api/ai-query', methods=['POST'])
def process_ai_query():
    """Process natural language query using AI"""
    if not require_login():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    query = data.get('query', '').strip()
    user_id = session['user']['id']
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    # Check if AI orchestrator is available
    if not ai_orchestrator:
        return jsonify({
            'success': True,
            'explanation': "🤖 **AI Assistant is currently unavailable**\n\n" \
                          "The AI engine is not configured or failed to initialize.\n\n" \
                          "**Try these instead:**\n" \
                          "1. Click on the example queries above\n" \
                          "2. Ask simpler questions like 'Show my productivity'\n" \
                          "3. Check if the MCP server is running on port 8000\n\n" \
                          "*Note: Basic productivity data will still work without AI.*",
            'data': [],
            'visualization_type': 'bar',
            'tool_calls': []
        })
    
    try:
        response = ai_orchestrator.process_query(user_id, query)
        
        return jsonify({
            'success': True,
            'explanation': response.get('explanation', ''),
            'data': response.get('data', []),
            'visualization_type': response.get('visualization_type', 'bar'),
            'tool_calls': response.get('tool_calls', [])
        })
        
    except Exception as e:
        print(f"AI query error: {e}")
        # Return a graceful error response instead of crashing
        return jsonify({
            'success': True,
            'explanation': f"🤖 **AI Assistant Encountered an Error**\n\n" \
                          f"**Your Query:** '{query}'\n\n" \
                          f"**What happened:** {str(e)}\n\n" \
                          f"**Suggestions:**\n" \
                          f"1. Try rephrasing your question\n" \
                          f"2. Use simpler language\n" \
                          f"3. Try one of the example queries\n" \
                          f"4. Check if the MCP server is running\n\n" \
                          f"*Example: 'Show my productivity for today'*",
            'data': [],
            'visualization_type': 'bar',
            'tool_calls': []
        })
# Add a link to AI assistant in your existing dashboards
# In user_dashboard.html and manager_dashboard.html, add:
# <a href="/ai-assistant" class="btn btn-primary">🤖 Ask AI Assistant</a>


if __name__ == '__main__':
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    
    app.run(debug=True, host='0.0.0.0', port=5000)