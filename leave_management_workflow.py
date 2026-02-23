from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
from datetime import date
from llm import is_leave_request, extract_leave_metadata, decide_leave_application, calculate_salary_deduction, \
                        draft_employee_decision_email, draft_finance_deduction_email
from tools.supabase_utils import is_employee, get_employee_details, create_employee_leave
from tools.oauth_utils import get_creds


creds = get_creds()
service = build("gmail", "v1", credentials=creds)


ALLOWED_DOMAINS = ["misl.org", "hassanrevel.com", "icloud.com"]
PROCESSED_LABEL_NAME = "MISL_PROCESSED"


def decode_body(msg_data: dict) -> str:
    body = ""
    if "parts" in msg_data["payload"]:
        for part in msg_data["payload"]["parts"]:
            if part["mimeType"] == "text/plain" and "data" in part["body"]:
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode()
    elif "body" in msg_data["payload"] and "data" in msg_data["payload"]["body"]:
        body = base64.urlsafe_b64decode(msg_data["payload"]["body"]["data"]).decode()
    return body

def send_email(to_email: str, subject: str, body: str) -> bool:
    try:
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

# -------------------------
# Main Workflow
# -------------------------
def process_incoming_emails(max_results: int = 10):
    results = service.users().messages().list(
                    userId="me",
                    maxResults=max_results
                ).execute()
    messages = results.get("messages", [])

    for msg in messages:
        try:
            msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
            headers = msg_data["payload"]["headers"]
            sender_email_subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "")
            sender_email_address = sender.split("<")[-1].replace(">", "").strip()

            print("processing email", sender_email_address)
            # 1. Validate domain
            domain = sender_email_address.split("@")[-1]
            if domain not in ALLOWED_DOMAINS:
                continue

            # 2. Validate employee
            if not is_employee(sender_email_address):
                print(f"⚠️ {sender_email_address} is NOT an employee, skipping...")
                continue

            sender_email_body = decode_body(msg_data)

            # 3. Check if leave request
            if not is_leave_request(sender_email_subject, sender_email_body):
                continue

            employee = get_employee_details(sender_email_address)
            leave_meta_info = extract_leave_metadata(sender_email_subject, sender_email_body)

            leave_start_raw = leave_meta_info.get("leave_start")
            leave_end_raw = leave_meta_info.get("leave_end")
            leave_start_date = parse_iso_date(leave_start_raw)
            leave_end_date = parse_iso_date(leave_end_raw)

            if not leave_start_date or not leave_end_date:
                print("⚠️ Missing leave dates, skipping request.")
                continue
            if leave_end_date < leave_start_date:
                print("⚠️ Invalid leave date range, skipping request.")
                continue

            prior_notice_days = (leave_start_date - date.today()).days
            leave_days = count_leave_days(leave_start_date, leave_end_date)
            if leave_days <= 0:
                print("⚠️ Invalid leave duration, skipping request.")
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
                    send_email("hassanrevelai@icloud.com", finance_email['subject'], finance_email['body'])
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
        except Exception as e:
            print(f"⚠️ Failed processing message {msg.get('id')}: {e}")
            continue

# -------------------------
# Run Workflow
# -------------------------
if __name__ == "__main__":
    process_incoming_emails()
