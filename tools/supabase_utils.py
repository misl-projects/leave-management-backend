from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, date
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
    annual_entitlement = int(employee_data.get("annual_leave_entitlement") or 0)
    current_year = date.today().year
    year_start = date(current_year, 1, 1)
    year_end = date(current_year, 12, 31)

    approved_days_current_year = 0
    for leave in employee_leaves_data:
        if leave.get("status") != "approved":
            continue

        leave_start = date.fromisoformat(str(leave.get("leave_start")))
        leave_end = date.fromisoformat(str(leave.get("leave_end")))

        overlap_start = max(leave_start, year_start)
        overlap_end = min(leave_end, year_end)

        if overlap_start <= overlap_end:
            approved_days_current_year += (overlap_end - overlap_start).days + 1

    remaining_employee_leaves = max(annual_entitlement - approved_days_current_year, 0)

    employee_data["approved_leave_days_current_year"] = approved_days_current_year
    employee_data["remaining_leaves"] = remaining_employee_leaves

    return employee_data

def calculate_prior_notice_days(leave_start: str) -> int:
    today = datetime.today().date()
    leave_start_date = datetime.strptime(leave_start, "%Y-%m-%d").date()

    prior_notice = (leave_start_date - today).days
    return prior_notice

def create_employee_leave(
    employee_id: str,
    leave_start: str,  # YYYY-MM-DD
    leave_end: str,    # YYYY-MM-DD
    status: str = "pending",
    leave_category: str | None = None,
    reason: str | None = None
) -> bool:

    # Normalize new leave dates
    leave_start_date = datetime.strptime(leave_start, "%Y-%m-%d").date()
    leave_end_date = datetime.strptime(leave_end, "%Y-%m-%d").date()

    # Calculate prior notice
    prior_notice_days = calculate_prior_notice_days(leave_start)

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
            return False

    # Insert new leave
    supabase.table("employee_leaves").insert({
        "employee_id": employee_id,
        "leave_start": leave_start,
        "leave_end": leave_end,
        "status": status,
        "leave_category": leave_category,
        "prior_notice_days": prior_notice_days,
        "reason": reason
    }).execute()

    return True

def get_employee_details_by_id(employee_id: str) -> dict | None:
    response = supabase.table("employees").select("*").eq("id", employee_id).limit(1).execute()
    if not response.data:
        return None
    return response.data[0]

def get_leave_by_id(leave_id: str) -> dict | None:
    response = supabase.table("employee_leaves").select("*").eq("id", leave_id).limit(1).execute()
    if not response.data:
        return None
    return response.data[0]

def fetch_pending_leave_status_events(limit: int = 20) -> list[dict]:
    response = (
        supabase.table("leave_status_change_events")
        .select("*")
        .eq("notification_status", "pending")
        .is_("notified_at", "null")
        .order("changed_at", desc=False)
        .limit(limit)
        .execute()
    )
    return response.data or []

def update_leave_status_event_result(
    event_id: int,
    notification_status: str,
    error_message: str | None = None
) -> None:
    payload = {
        "notification_status": notification_status,
        "notified_at": datetime.utcnow().isoformat()
    }
    if error_message:
        payload["error_message"] = error_message[:1000]
    supabase.table("leave_status_change_events").update(payload).eq("id", event_id).execute()
