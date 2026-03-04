from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
import os
import threading
from datetime import date
from llm import is_leave_request, extract_leave_metadata, decide_leave_application, calculate_salary_deduction, \
                        draft_employee_decision_email, draft_finance_deduction_email, draft_admin_override_email
from tools.supabase_utils import (
    is_employee,
    get_employee_details,
    create_employee_leave,
    get_employee_details_by_id,
    get_leave_by_id,
    fetch_pending_leave_status_events,
    update_leave_status_event_result
)
from tools.oauth_utils import get_creds


_thread_local = threading.local()
_gmail_service_init_lock = threading.Lock()


ALLOWED_DOMAINS = ["misl.org", "hassanrevel.com", "icloud.com"]
PROCESSED_LABEL_NAME = "MISL_LEAVE_PROCESSED"
FINANCE_EMAIL = os.environ.get("FINANCE_EMAIL", "hassanrevelai@icloud.com")
_processed_label_id_cache: str | None = None


def decode_body(msg_data: dict) -> str:
    body = ""
    if "parts" in msg_data["payload"]:
        for part in msg_data["payload"]["parts"]:
            if part["mimeType"] == "text/plain" and "data" in part["body"]:
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode()
    elif "body" in msg_data["payload"] and "data" in msg_data["payload"]["body"]:
        body = base64.urlsafe_b64decode(msg_data["payload"]["body"]["data"]).decode()
    return body

def get_gmail_service():
    """
    Gmail API client is not guaranteed to be thread-safe.
    Keep one client per worker thread to avoid SSL transport corruption.
    """
    service = getattr(_thread_local, "gmail_service", None)
    if service is None:
        with _gmail_service_init_lock:
            service = getattr(_thread_local, "gmail_service", None)
            if service is None:
                creds = get_creds()
                service = build("gmail", "v1", credentials=creds)
                _thread_local.gmail_service = service
    return service

def send_email(to_email: str, subject: str, body: str) -> bool:
    try:
        service = get_gmail_service()
        # Create MIME message
        message = MIMEText(body)
        message['to'] = to_email
        message['subject'] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        # Send via Gmail API
        message_obj = {'raw': raw_message}
        service.users().messages().send(userId="me", body=message_obj).execute()

        return True
    except Exception as e:
        print(f"⚠️ Failed to send email to {to_email}: {e}")
        return False

def get_or_create_processed_label_id() -> str | None:
    global _processed_label_id_cache
    if _processed_label_id_cache:
        return _processed_label_id_cache

    try:
        service = get_gmail_service()
        labels = service.users().labels().list(userId="me").execute().get("labels", [])
        for label in labels:
            if label.get("name") == PROCESSED_LABEL_NAME:
                _processed_label_id_cache = label.get("id")
                return _processed_label_id_cache

        created = service.users().labels().create(
            userId="me",
            body={
                "name": PROCESSED_LABEL_NAME,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show"
            }
        ).execute()
        _processed_label_id_cache = created.get("id")
        print(f"✅ Created Gmail label: {PROCESSED_LABEL_NAME}")
        return _processed_label_id_cache
    except Exception as e:
        print(f"⚠️ Could not get/create processed label {PROCESSED_LABEL_NAME}: {e}")
        return None

def mark_message_processed(message_id: str, processed_label_id: str | None) -> None:
    if not processed_label_id:
        return
    try:
        service = get_gmail_service()
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [processed_label_id]}
        ).execute()
    except Exception as e:
        print(f"⚠️ Failed to label message {message_id} as processed: {e}")

def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None

def count_leave_days(start: date, end: date) -> int:
    if end < start:
        return 0
    return (end - start).days + 1

def process_status_change_notifications(limit: int = 20):
    """
    Sends employee/finance notifications when admins override leave status in dashboard.
    Trigger source is the DB queue table `leave_status_change_events`.
    """
    events = fetch_pending_leave_status_events(limit=limit)
    if not events:
        return

    for event in events:
        event_id = event["id"]
        try:
            leave_id = event.get("leave_id")
            employee_id = event.get("employee_id")
            old_status = (event.get("old_status") or "").lower()
            new_status = (event.get("new_status") or "").lower()

            if not leave_id or not employee_id:
                update_leave_status_event_result(event_id, "failed", "Missing leave_id or employee_id.")
                continue

            employee = get_employee_details_by_id(employee_id)
            leave_row = get_leave_by_id(leave_id)
            if not employee or not leave_row:
                update_leave_status_event_result(event_id, "failed", "Missing employee or leave record.")
                continue

            leave_salary_deduction = calculate_salary_deduction(
                employee_salary=employee.get("basic_salary") or 0,
                leave_start=leave_row.get("leave_start"),
                leave_end=leave_row.get("leave_end"),
                leave_decision=new_status
            )

            employee_email = draft_admin_override_email(
                employee_name=employee.get("full_name") or "Employee",
                employee_position=employee.get("position") or "",
                remaining_leaves=employee.get("remaining_leaves"),
                leave_start=leave_row.get("leave_start"),
                leave_end=leave_row.get("leave_end"),
                leave_reason=leave_row.get("reason"),
                old_status=old_status,
                new_status=new_status,
                leave_salary_deduction=leave_salary_deduction,
            )

            employee_sent = send_email(
                employee.get("company_email"),
                employee_email.get("subject", "Leave Request Status Updated"),
                employee_email.get("body", "")
            )
            if not employee_sent:
                update_leave_status_event_result(event_id, "failed", "Employee email sending failed.")
                continue

            # Notify finance whenever updated status becomes rejected.
            if new_status == "rejected":
                finance_email = draft_finance_deduction_email(
                    employee_name=employee.get("full_name") or "Employee",
                    employee_position=employee.get("position") or "",
                    employee_salary=employee.get("basic_salary") or 0,
                    annual_leaves=employee.get("annual_leave_entitlement") or 0,
                    remaining_leaves=employee.get("leave_balance") or 0,
                    leave_category=leave_row.get("leave_category"),
                    leave_reason=leave_row.get("reason"),
                    leave_start=leave_row.get("leave_start"),
                    leave_end=leave_row.get("leave_end"),
                    email_subject=f"Admin override {old_status} -> {new_status}",
                    email_body="Admin changed leave request status manually in dashboard.",
                    leave_decision=new_status,
                    leave_salary_deduction=leave_salary_deduction
                )
                finance_sent = send_email(
                    FINANCE_EMAIL,
                    finance_email.get("subject", "Leave Status Updated"),
                    finance_email.get("body", "")
                )
                if not finance_sent:
                    update_leave_status_event_result(event_id, "failed", "Finance email sending failed.")
                    continue

            update_leave_status_event_result(event_id, "sent")
            print(f"✅ Status override notification sent for event #{event_id} ({old_status} -> {new_status})")
        except Exception as e:
            update_leave_status_event_result(event_id, "failed", str(e))
            print(f"⚠️ Failed processing status-change event #{event_id}: {e}")

# -------------------------
# Main Workflow
# -------------------------
def process_incoming_emails(max_results: int = 10):
    service = get_gmail_service()
    processed_label_id = get_or_create_processed_label_id()
    results = service.users().messages().list(
                    userId="me",
                    maxResults=max_results
                ).execute()
    messages = results.get("messages", [])

    for msg in messages:
        message_id = msg["id"]
        try:
            msg_data = service.users().messages().get(userId="me", id=message_id).execute()
            label_ids = set(msg_data.get("labelIds", []))
            if processed_label_id and processed_label_id in label_ids:
                continue

            headers = msg_data["payload"]["headers"]
            sender_email_subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "")
            sender_email_address = sender.split("<")[-1].replace(">", "").strip()

            print("processing email", sender_email_address)
            # 1. Validate domain
            domain = sender_email_address.split("@")[-1]
            if domain not in ALLOWED_DOMAINS:
                mark_message_processed(message_id, processed_label_id)
                continue

            # 2. Validate employee
            if not is_employee(sender_email_address):
                print(f"⚠️ {sender_email_address} is NOT an employee, skipping...")
                mark_message_processed(message_id, processed_label_id)
                continue

            sender_email_body = decode_body(msg_data)

            # 3. Check if leave request
            if not is_leave_request(sender_email_subject, sender_email_body):
                mark_message_processed(message_id, processed_label_id)
                continue

            employee = get_employee_details(sender_email_address)
            leave_meta_info = extract_leave_metadata(sender_email_subject, sender_email_body)

            leave_start_raw = leave_meta_info.get("leave_start")
            leave_end_raw = leave_meta_info.get("leave_end")
            leave_start_date = parse_iso_date(leave_start_raw)
            leave_end_date = parse_iso_date(leave_end_raw)

            if not leave_start_date or not leave_end_date:
                print("⚠️ Missing leave dates, skipping request.")
                mark_message_processed(message_id, processed_label_id)
                continue
            if leave_end_date < leave_start_date:
                print("⚠️ Invalid leave date range, skipping request.")
                mark_message_processed(message_id, processed_label_id)
                continue

            prior_notice_days = (leave_start_date - date.today()).days
            leave_days = count_leave_days(leave_start_date, leave_end_date)
            if leave_days <= 0:
                print("⚠️ Invalid leave duration, skipping request.")
                mark_message_processed(message_id, processed_label_id)
                continue

            leave_decision = decide_leave_application(
                employee_name=employee['full_name'],
                employee_position=employee["position"],
                employee_salary=employee["basic_salary"],
                annual_leaves=employee["annual_leave_entitlement"],
                remaining_leaves=employee["remaining_leaves"],
                leave_category=leave_meta_info.get("leave_category"),
                leave_reason=leave_meta_info.get("leave_reason"),
                leave_start=leave_start_raw,
                leave_end=leave_end_raw,
                prior_notice_days=prior_notice_days,
                leave_days=leave_days,
                email_subject=sender_email_subject,
                email_body=sender_email_body
            )

            if leave_decision not in {"approved", "pending", "rejected"}:
                leave_decision = "pending"

            leave_salary_deduction = calculate_salary_deduction(
                employee_salary=employee["basic_salary"],
                leave_start=leave_start_raw,
                leave_end=leave_end_raw,
                leave_decision=leave_decision
            )

            employee_email = draft_employee_decision_email(
                employee_name=employee['full_name'],
                employee_position=employee["position"],
                employee_salary=employee["basic_salary"],
                annual_leaves=employee["annual_leave_entitlement"],
                remaining_leaves=employee["remaining_leaves"],
                leave_reason=leave_meta_info.get("leave_reason"),
                leave_category=leave_meta_info.get("leave_category"),
                leave_start=leave_start_raw,
                leave_end=leave_end_raw,
                email_subject=sender_email_subject,
                email_body=sender_email_body,
                leave_decision=leave_decision,
                leave_salary_deduction=leave_salary_deduction,
                prior_notice_days=prior_notice_days
            )

            finance_email = None
            if leave_decision == "rejected":
                finance_email = draft_finance_deduction_email(
                    employee_name=employee['full_name'],
                    employee_position=employee["position"],
                    employee_salary=employee["basic_salary"],
                    annual_leaves=employee["annual_leave_entitlement"],
                    remaining_leaves=employee["remaining_leaves"],
                    leave_category=leave_meta_info.get("leave_category"),
                    leave_reason=leave_meta_info.get("leave_reason"),
                    leave_start=leave_start_raw,
                    leave_end=leave_end_raw,
                    email_subject=sender_email_subject,
                    email_body=sender_email_body,
                    leave_decision=leave_decision,
                    leave_salary_deduction=leave_salary_deduction
                )

            inserted = create_employee_leave(
                employee_id=employee['id'],
                leave_start=leave_start_raw,
                leave_end=leave_end_raw,
                status=leave_decision,
                leave_category=leave_meta_info.get('leave_category'),
                reason=leave_meta_info.get('leave_reason')
            )

            if inserted:
                print("✅ Leave request recorded in Supabase.")
                send_email(employee['company_email'], employee_email['subject'], employee_email['body'])

                if leave_decision == "rejected" and finance_email:
                    send_email(FINANCE_EMAIL, finance_email['subject'], finance_email['body'])
            else:
                print("ℹ️ Identical leave request fingerprint found. Skipping emails and insert.")

            print("------------------------------------------------")
            print(f"📨 Incoming Leave Request from ({sender_email_address})")
            print(f"Subject: {sender_email_subject}")
            print(f"Body:\n{sender_email_body}")
            print("Employee:", employee)
            print("Leave Metadata:", leave_meta_info)
            print("Leave decision:", leave_decision)
            print("Prior notice days:", prior_notice_days)
            print("Leave salary deduction:", leave_salary_deduction)
            print("Employee Email:", employee_email)
            if finance_email:
                print("Finance Email:", finance_email)
            print("Leave Request Recorded:", inserted)
            print("------------------------------------------------")
            mark_message_processed(message_id, processed_label_id)
        except Exception as e:
            print(f"⚠️ Failed processing message {msg.get('id')}: {e}")
            continue

# -------------------------
# Run Workflow
# -------------------------
if __name__ == "__main__":
    process_incoming_emails()
