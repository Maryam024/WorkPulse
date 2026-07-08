# frontend/routes.py
from app import app, supabase, ai_orchestrator, email_sender, password_recovery
from app import (
    require_login, get_user_settings, update_user_theme, generate_temp_password,
    calculate_productivity_stats, get_user_activity_data, send_welcome_email_to_manager,
    send_user_credentials, send_weekly_report, send_scheduled_weekly_reports
)
from flask import render_template, request, redirect, url_for, session, jsonify, flash, make_response
from datetime import datetime, timezone, timedelta
import os
from supabase import create_client
import threading
import random
import schedule
import time

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
    today_stats = calculate_productivity_stats(today_activities)  # Now includes minutes!
    
    # Get minutes from the updated function
    productive_minutes = today_stats.get('productive_minutes', 0)
    idle_minutes = today_stats.get('idle_minutes', 0)
    total_minutes = productive_minutes + idle_minutes
    
    # ADD: Calculate hourly breakdown for the day
    hourly_data = []
    current_hour = datetime.now().hour
    
    # Mock hourly data (in production, get from activity logs)
    for hour in range(9, 18):  # 9 AM to 5 PM
        if hour <= current_hour:
            productive = random.randint(30, 55)  # 30-55 minutes productive per hour
            idle = 60 - productive  # Remainder is idle
        else:
            productive = 0
            idle = 0
            
        hourly_data.append({
            'hour': f"{hour}:00",
            'productive_minutes': productive,
            'idle_minutes': idle,
            'productivity_score': round((productive / 60) * 100) if productive > 0 else 0
        })
    
    return jsonify({
        'today_stats': today_stats,
        'user': session.get('user'),
        # ADD THESE NEW FIELDS:
        'minutes_breakdown': {
            'productive_minutes': productive_minutes,
            'idle_minutes': idle_minutes,
            'total_minutes': total_minutes,
            'productive_percentage': round((productive_minutes / total_minutes) * 100) if total_minutes > 0 else 0
        },
        'hourly_data': hourly_data,
        'current_session': {
            'is_active': len(today_activities) > 0,
            'last_activity': today_activities[0]['timestamp'] if today_activities else None,
            'active_since': today_activities[-1]['timestamp'] if today_activities else None
        }
    })

@app.route('/manager/dashboard')
def manager_dashboard():
    if not require_login('manager'):
        return redirect(url_for('login'))
    
    manager_id = session['user']['id']
    org_id = session['user'].get('organization_id')
    
    # Get all users in organization
    users_resp = supabase.table("profiles").select("*").eq("organization_id", org_id).execute()
    users = users_resp.data or []
    
    # Get team stats - UPDATE TO INCLUDE MINUTES
    team_stats = []
    total_productive_minutes = 0  # CHANGE TO MINUTES
    total_idle_minutes = 0  # CHANGE TO MINUTES
    
    for user in users:
        if user['role'] == 'user':
            user_activities = get_user_activity_data(user['id'], days=1)
            user_stats = calculate_productivity_stats(user_activities)
            
            # Calculate minutes
            productive_minutes = user_stats.get('productive_minutes', 0)
            idle_minutes = user_stats.get('idle_minutes', 0)
            
            is_online = len(user_activities) > 0 and (
                datetime.now(timezone.utc) - datetime.fromisoformat(user_activities[0]['timestamp'].replace('Z', '+00:00'))
            ).total_seconds() < 300
            
            team_stats.append({
                'user': user, 
                'stats': user_stats, 
                'is_online': is_online,
                'productivity_score': user_stats['productivity_score'],
                # ADD MINUTES DATA:
                'productive_minutes': productive_minutes,
                'idle_minutes': idle_minutes,
                'total_minutes': productive_minutes + idle_minutes,
                'hours_worked_today': round((productive_minutes + idle_minutes) / 60, 1)
            })
            
            total_productive_minutes += productive_minutes
            total_idle_minutes += idle_minutes
    
    # Calculate overall in minutes
    total_minutes = total_productive_minutes + total_idle_minutes
    avg_productivity = (total_productive_minutes / total_minutes * 100) if total_minutes > 0 else 0
    
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
                               'overall_productivity': round(avg_productivity, 1),
                               # ADD MINUTES METRICS:
                               'total_productive_minutes': total_productive_minutes,
                               'total_productive_hours': round(total_productive_minutes / 60, 1),
                               'total_idle_minutes': total_idle_minutes,
                               'total_idle_hours': round(total_idle_minutes / 60, 1),
                               'avg_minutes_per_employee': round(total_minutes / len(team_stats)) if team_stats else 0
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
            send_user_credentials(
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

@app.route('/api/real-time-stats')
def real_time_stats():
    """Get real-time productivity stats (updated every minute)"""
    if not require_login():
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user']['id']
    role = session.get('role', 'user')
    
    # Get last 15 minutes of activity
    fifteen_min_ago = datetime.now(timezone.utc) - timedelta(minutes=15)
    
    try:
        response = supabase.table("user_activity").select("*").eq(
            "user_id", user_id
        ).gte(
            "timestamp", fifteen_min_ago.isoformat()
        ).order("timestamp", desc=True).execute()
        
        recent_activities = response.data or []
        
        # Calculate current session stats
        if recent_activities:
            # Group by minute for granular tracking
            from collections import defaultdict
            minute_data = defaultdict(lambda: {'productive': 0, 'idle': 0})
            
            for i in range(len(recent_activities) - 1):
                current = recent_activities[i]
                next_act = recent_activities[i + 1]
                
                try:
                    current_time = datetime.fromisoformat(current['timestamp'].replace('Z', '+00:00'))
                    next_time = datetime.fromisoformat(next_act['timestamp'].replace('Z', '+00:00'))
                    
                    # Get minute of the hour
                    minute_key = current_time.strftime("%H:%M")
                    
                    delta_seconds = (next_time - current_time).total_seconds()
                    if delta_seconds > 0:
                        if "idle" in current['event'].lower():
                            minute_data[minute_key]['idle'] += delta_seconds
                        else:
                            minute_data[minute_key]['productive'] += delta_seconds
                except:
                    continue
            
            # Convert to per-minute stats
            minute_stats = []
            for minute, data in minute_data.items():
                total_seconds = data['productive'] + data['idle']
                if total_seconds > 0:
                    minute_stats.append({
                        'minute': minute,
                        'productive_seconds': data['productive'],
                        'idle_seconds': data['idle'],
                        'productivity_percentage': (data['productive'] / total_seconds) * 100
                    })
            
            # Sort by minute
            minute_stats.sort(key=lambda x: x['minute'])
            
            # Current status
            last_activity = recent_activities[0]
            is_currently_idle = "idle" in last_activity['event'].lower()
            
            return jsonify({
                'success': True,
                'current_status': 'idle' if is_currently_idle else 'active',
                'last_activity_time': last_activity['timestamp'],
                'minute_by_minute': minute_stats[-10:],  # Last 10 minutes
                'total_recent_minutes': len(minute_stats),
                'productive_recent_seconds': sum(m['productive_seconds'] for m in minute_stats),
                'idle_recent_seconds': sum(m['idle_seconds'] for m in minute_stats)
            })
        else:
            return jsonify({
                'success': True,
                'current_status': 'inactive',
                'message': 'No recent activity'
            })
            
    except Exception as e:
        print(f"Real-time stats error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Add this endpoint to app.py
@app.route('/api/real-time-team')
def real_time_team():
    """Get real-time team minutes data"""
    if not require_login('manager'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    manager_id = session['user']['id']
    org_id = session['user'].get('organization_id')
    
    try:
        # Get all users in organization
        users_resp = supabase.table("profiles").select("*").eq("organization_id", org_id).execute()
        users = users_resp.data or []
        
        team_data = []
        total_productive_minutes = 0
        total_idle_minutes = 0
        online_count = 0
        working_count = 0
        idle_count = 0
        
        for user in users:
            if user['role'] == 'user':
                # Get today's activities
                user_activities = get_user_activity_data(user['id'], days=1)
                user_stats = calculate_productivity_stats(user_activities)
                
                productive_minutes = user_stats.get('productive_minutes', 0)
                idle_minutes = user_stats.get('idle_minutes', 0)
                total_minutes = productive_minutes + idle_minutes
                
                # Determine status
                is_online = len(user_activities) > 0 and (
                    datetime.now(timezone.utc) - datetime.fromisoformat(user_activities[0]['timestamp'].replace('Z', '+00:00'))
                ).total_seconds() < 300
                
                # Determine if working (productive in last 5 minutes)
                is_working = False
                last_activity_time = None
                if user_activities:
                    last_activity_time = user_activities[0]['timestamp']
                    # Check if last activity was "active" (not idle)
                    if is_online and "idle" not in user_activities[0]['event'].lower():
                        is_working = True
                
                if is_online:
                    online_count += 1
                    if is_working:
                        working_count += 1
                    else:
                        idle_count += 1
                
                team_data.append({
                    'user_id': user['id'],
                    'name': user['name'],
                    'is_online': is_online,
                    'is_working': is_working,
                    'last_activity': last_activity_time,
                    'productive_minutes': productive_minutes,
                    'idle_minutes': idle_minutes,
                    'total_minutes': total_minutes,
                    'productivity_score': user_stats['productivity_score']
                })
                
                total_productive_minutes += productive_minutes
                total_idle_minutes += idle_minutes
        
        # Calculate averages
        team_size = len(team_data)
        avg_minutes_per_employee = total_productive_minutes / team_size if team_size > 0 else 0
        
        total_minutes = total_productive_minutes + total_idle_minutes
        avg_productivity = (total_productive_minutes / total_minutes * 100) if total_minutes > 0 else 0
        
        return jsonify({
            'success': True,
            'team_size': team_size,
            'online_count': online_count,
            'working_count': working_count,
            'idle_count': idle_count,
            'total_productive_minutes': total_productive_minutes,
            'total_idle_minutes': total_idle_minutes,
            'avg_minutes_per_employee': avg_minutes_per_employee,
            'avg_productivity': avg_productivity,
            'members': team_data,
            'updated_at': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        print(f"Real-time team error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

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

@app.route('/manager/api/delete-user/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    if not require_login('manager'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get user email before deletion for notification
        user_resp = supabase.table("profiles").select("email").eq("id", user_id).execute()
        
        if not user_resp.data:
            return jsonify({'error': 'User not found'}), 404
        
        user_email = user_resp.data[0]['email'] if user_resp.data else None
        
        # IMPORTANT: Delete in correct order due to foreign keys
        # 1. First delete from user_settings (child table)
        supabase.table("user_settings").delete().eq("user_id", user_id).execute()
        
        # 2. Then delete from profiles (parent table)
        supabase.table("profiles").delete().eq("id", user_id).execute()
        
        # 3. Also check for other related tables that might reference the user
        # For example, if you have time_tracking, tasks, etc.
        try:
            # Check and delete from time_tracking if it exists
            supabase.table("time_tracking").delete().eq("user_id", user_id).execute()
        except:
            pass  # Table might not exist
        
        try:
            # Check and delete from tasks if it exists
            supabase.table("tasks").delete().eq("assigned_to", user_id).execute()
        except:
            pass
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting user {user_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add this endpoint that filters by current manager
@app.route('/manager/api/refresh-users', methods=['GET'])
def refresh_users():
    if not require_login('manager'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get current manager's ID from session
        current_manager_id = session.get('user', {}).get('id')
        if not current_manager_id:
            return jsonify({'error': 'Manager not found in session'}), 401
        
        # Fetch only users for this manager - adjust the query based on your schema
        # Assuming you have a 'manager_id' column in profiles table
        resp = supabase.table("profiles").select("*").eq("manager_id", current_manager_id).execute()
        
        users = []
        for user in resp.data:
            # Get user stats
            stats_resp = supabase.table("user_settings").select("*").eq("user_id", user['id']).execute()
            stats = stats_resp.data[0] if stats_resp.data else {}
            
            users.append({
                'id': user['id'],
                'name': user.get('name'),
                'email': user.get('email'),
                'is_active': user.get('is_active', True),
                'productivity_score': stats.get('productivity_score', 0),
                'productive_hours': stats.get('productive_hours', 0),
                'idle_hours': stats.get('idle_hours', 0)
            })
        
        return jsonify({
            'success': True,
            'users': users
        })
        
    except Exception as e:
        print(f"Error refreshing users: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Also update the get-user endpoint to check manager permissions
@app.route('/manager/api/get-user/<user_id>', methods=['GET'])
def get_user(user_id):
    if not require_login('manager'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get current manager's ID
        current_manager_id = session.get('user', {}).get('id')
        
        # Fetch user with manager check
        resp = supabase.table("profiles").select("*").eq("id", user_id).eq("manager_id", current_manager_id).execute()
        
        if not resp.data:
            return jsonify({'error': 'User not found or unauthorized'}), 404
        
        user = resp.data[0]
        return jsonify({
            'success': True,
            'user': {
                'id': user.get('id'),
                'name': user.get('name'),
                'email': user.get('email'),
                'is_active': user.get('is_active', True)
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Update the update-user endpoint to check manager permissions
@app.route('/manager/api/update-user/<user_id>', methods=['POST'])
def update_user(user_id):
    if not require_login('manager'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    name = data.get('name')
    is_active = data.get('is_active')
    
    try:
        # Check if user belongs to current manager
        current_manager_id = session.get('user', {}).get('id')
        user_check = supabase.table("profiles").select("id").eq("id", user_id).eq("manager_id", current_manager_id).execute()
        
        if not user_check.data:
            return jsonify({'error': 'User not found or unauthorized'}), 404
        
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
    user_role = session.get('role', 'user')
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    # Always ensure ai_orchestrator exists
    if not ai_orchestrator:
        return jsonify({
            'success': True,
            'explanation': "🤖 **AI Assistant is initializing...**\n\nPlease try again in a moment.",
            'data': [],
            'visualization_type': 'bar',
            'tool_calls': [],
            'intent': 'initializing'
        })
    
    try:
        response = ai_orchestrator.process_query(user_id, query)
        
        return jsonify({
            'success': True,
            'explanation': response.get('explanation', ''),
            'data': response.get('data', []),
            'visualization_type': response.get('visualization_type', 'bar'),
            'tool_calls': response.get('tool_calls', []),
            'intent': response.get('intent', 'unknown')
        })
        
    except Exception as e:
        print(f"AI query error: {e}")
        # Return a working response even on error
        return jsonify({
            'success': True,
            'explanation': f"🤖 **WorkPulse Assistant**\n\n**Query:** '{query}'\n\nI'm having trouble with the AI engine right now.\n\n**Try clicking on one of the example queries** - they'll work even without AI!",
            'data': [],
            'visualization_type': 'bar',
            'tool_calls': [],
            'intent': 'error_fallback'
        })

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page"""
    if request.method == 'POST':
        email = request.form['email']
        
        try:
            # Check if user exists
            profile_response = supabase.table("profiles").select("*").eq("email", email).execute()
            
            if not profile_response.data:
                # Don't reveal if user exists (security best practice)
                flash("If an account exists with this email, you'll receive a reset link.", "info")
                return redirect(url_for('login'))
            
            user = profile_response.data[0]
            user_id = user['id']
            
            # Generate reset token
            token = password_recovery.generate_reset_token(user_id)
            
            # Send reset email
            password_recovery.send_reset_email(email, token)
            
            flash("Password reset link has been sent to your email.", "success")
            return redirect(url_for('login'))
            
        except Exception as e:
            flash("An error occurred. Please try again.", "danger")
            return render_template('forgot_password.html')
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password using token"""
    print(f"🔑 Validating token: {token}")
    
    # Validate token
    validation = password_recovery.validate_token(token)
    print(f"📋 Validation result: {validation}")
    
    if not validation["valid"]:
        flash(f"Token validation failed: {validation['error']}", "danger")
        return redirect(url_for('forgot_password'))
    
    # Get user email for display
    user_email = validation.get("user_email", "Unknown User")
    
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        # Validate passwords
        if new_password != confirm_password:
            flash("Passwords do not match", "danger")
            return render_template('reset_password.html', token=token, user_email=user_email)
        
        if len(new_password) < 8:
            flash("Password must be at least 8 characters", "danger")
            return render_template('reset_password.html', token=token, user_email=user_email)
        
        try:
            # Get service role key for admin operations
            service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            admin_client = create_client(os.getenv("SUPABASE_URL"), service_key)
            
            # Update password using admin API
            admin_client.auth.admin.update_user_by_id(
                validation["user_id"],
                {"password": new_password}
            )
            
            # Mark token as used
            password_recovery.mark_token_used(token)
            
            # Update profile to mark password as permanent
            supabase.table("profiles").update({
                "temp_password": False,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", validation["user_id"]).execute()
            
            flash("✅ Password has been reset successfully! You can now login.", "success")
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"❌ Password reset error: {e}")
            flash(f"Failed to reset password: {str(e)}", "danger")
            return render_template('reset_password.html', token=token, user_email=user_email)
    
    return render_template('reset_password.html', token=token, user_email=user_email)

