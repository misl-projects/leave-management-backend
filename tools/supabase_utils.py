from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()

# -------------------------
# Supabase Setup
# -------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------
# Helpers
# -------------------------
def is_employee(email: str) -> bool:
    response = supabase.table("employees").select("company_email").eq("company_email", email).execute()
    return len(response.data) > 0

def get_employee_details(email: str) -> dict:
    employee_data = supabase.table("employees").select("*").eq("company_email", email).execute().data[0]

    employee_leaves_data = supabase.table("employee_leaves").select("*").eq("employee_id", employee_data['id']).execute().data
    remaining_employee_leaves = employee_data['annual_leave_entitlement'] - len([l['status']=='approved' for l in employee_leaves_data])

    employee_data['remaining_leaves'] = remaining_employee_leaves

    return employee_data


def create_employee_leave(
    employee_id: str,
    leave_start: str,  # YYYY-MM-DD
    leave_end: str,    # YYYY-MM-DD
    status: str = "pending",
    prior_notice_days: int = 3,
    reason: str | None = None
) -> bool:
    """
    Inserts a leave request into employee_leaves if not already present.

    Returns True if inserted, False if duplicate exists.
    """

    # Normalize new leave dates
    leave_start_date = datetime.strptime(leave_start, "%Y-%m-%d").date()
    leave_end_date = datetime.strptime(leave_end, "%Y-%m-%d").date()

    # Fetch existing leaves for the employee
    existing_leaves = supabase.table("employee_leaves")\
        .select("*")\
        .eq("employee_id", employee_id)\
        .execute().data

    for leave in existing_leaves:
        # Convert existing leave strings to date
        existing_start = datetime.strptime(leave['leave_start'], "%Y-%m-%d").date()
        existing_end = datetime.strptime(leave['leave_end'], "%Y-%m-%d").date()

        # Check for overlapping leave
        if leave_start_date <= existing_end and leave_end_date >= existing_start:
            return False  # Duplicate / overlapping leave exists

    # Insert new leave
    supabase.table("employee_leaves").insert({
        "employee_id": employee_id,
        "leave_start": leave_start,
        "leave_end": leave_end,
        "status": status,
        "prior_notice_days": prior_notice_days,
        "reason": reason
    }).execute()

    return True