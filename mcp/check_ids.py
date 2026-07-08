# check_ids.py
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

print("🔍 Checking database structure...")

# 1. Check profiles table
print("\n📋 Profiles Table:")
response = supabase.table("profiles").select("id, email, name, role, manager_id, is_active, created_at").limit(10).execute()
for profile in response.data:
    print(f"  ID: {profile['id']}")
    print(f"    Name: {profile.get('name', 'N/A')}")
    print(f"    Email: {profile.get('email', 'N/A')}")
    print(f"    Role: {profile.get('role', 'N/A')}")
    print(f"    Manager ID: {profile.get('manager_id', 'N/A')}")
    print()

# 2. Check user_activity table structure
print("\n📊 User Activity Table Structure:")
response = supabase.table("user_activity").select("*").limit(1).execute()
if response.data:
    print("  Columns:", list(response.data[0].keys()))

# 3. Count records
print("\n📈 Record Counts:")
profiles_count = supabase.table("profiles").select("*", count="exact").execute()
activities_count = supabase.table("user_activity").select("*", count="exact").execute()
print(f"  Profiles: {profiles_count.count}")
print(f"  Activities: {activities_count.count}")

# 4. Check for any users with custom_id
print("\n🔎 Checking for custom_id field:")
try:
    response = supabase.table("profiles").select("id, custom_id").not_.is_("custom_id", "null").limit(5).execute()
    if response.data:
        print("  Users with custom_id:")
        for user in response.data:
            print(f"    {user['id']}: custom_id = {user.get('custom_id')}")
    else:
        print("  No custom_id field found")
except Exception as e:
    print(f"  Error checking custom_id: {e}")