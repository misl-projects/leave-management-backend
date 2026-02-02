from langchain_groq import ChatGroq
from langchain.messages import HumanMessage
from dotenv import load_dotenv
from time import sleep
import json

load_dotenv()

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    max_tokens=1000
)

# -------------------------
# 1️⃣ Employee Rejection Email
# -------------------------
def draft_employee_rejection_email(
    employee_name: str,
    employee_position: str,
    employee_salary: float,
    annual_leaves: int,
    remaining_leaves: int,
    leave_category: str | None,
    leave_reason: str | None,
    leave_start: str | None,
    leave_end: str | None,
    email_subject: str,
    email_body: str,
    leave_decision: str,
    leave_salary_deduction: float,
    max_retries: int = 3
) -> dict:
    """
    Drafts a polite HR email to the employee explaining leave rejection due to insufficient prior notice.
    Returns a dict with 'subject' and 'body'.
    If LLM fails to return valid JSON, uses a fallback email.
    """

    prompt = f"""
You are an HR assistant drafting an email to an employee.

Rules:
- Leave request is rejected due to insufficient prior notice.
- Include remaining leaves in the email.
- Reference the leave dates and reason.
- Use professional, calm, and neutral tone.
- Do NOT include salary deduction in employee email.
- Output ONLY valid JSON with keys "subject" and "body".

Employee Info:
Name: {employee_name}
Position: {employee_position}
Annual Leaves: {annual_leaves}
Remaining Leaves: {remaining_leaves}

Leave Info:
Category: {leave_category}
Reason: {leave_reason}
Start Date: {leave_start}
End Date: {leave_end}

Original Email:
Subject: {email_subject}
Body:
{email_body}

HR Decision: {leave_decision}
"""

    for attempt in range(max_retries):
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"⚠️ LLM JSON parse failed (attempt {attempt+1}/{max_retries}). Retrying...")
            sleep(1)  # short delay before retry

    # fallback if LLM keeps failing
    fallback_subject = f"Leave Request Update: {leave_start} to {leave_end}"
    fallback_body = (
        f"Dear {employee_name},\n\n"
        f"Your leave request from {leave_start} to {leave_end} cannot be accepted due to insufficient prior notice.\n"
        f"You have {remaining_leaves} leave(s) remaining.\n\n"
        "Please reach out to HR for any clarification.\n\nBest regards,\nHR Department"
    )
    return {"subject": fallback_subject, "body": fallback_body}


# -------------------------
# 2️⃣ Finance Notification Email
# -------------------------
def draft_finance_deduction_email(
    employee_name: str,
    employee_position: str,
    employee_salary: float,
    annual_leaves: int,
    remaining_leaves: int,
    leave_category: str | None,
    leave_reason: str | None,
    leave_start: str | None,
    leave_end: str | None,
    email_subject: str,
    email_body: str,
    leave_decision: str,
    leave_salary_deduction: float,
    max_retries: int = 3
) -> dict:
    """
    Drafts an internal email to Finance to deduct salary for unauthorized leave.
    Returns a dict with 'subject' and 'body'.
    """
    prompt = f"""
You are an HR assistant drafting an internal email to Finance.

Rules:
- Triggered when leave is rejected.
- Include employee name, position, leave dates, and days.
- Include amount to deduct from salary: {leave_salary_deduction}.
- Use formal, neutral, and direct tone.
- Output ONLY valid JSON with keys "subject" and "body".

Employee Info:
Name: {employee_name}
Position: {employee_position}
Salary: {employee_salary}

Leave Info:
Category: {leave_category}
Reason: {leave_reason}
Start Date: {leave_start}
End Date: {leave_end}

Original Employee Email:
Subject: {email_subject}
Body:
{email_body}

HR Decision: {leave_decision}
Salary Deduction: {leave_salary_deduction}
"""
    for attempt in range(max_retries):
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"⚠️ Finance LLM JSON parse failed (attempt {attempt+1}/{max_retries}). Retrying...")
            sleep(1)
    # fallback
    body = (
        f"Dear Finance Team,\n\n"
        f"The leave request submitted by {employee_name}, {employee_position}, "
        f"from {leave_start} to {leave_end} "
        f"has been rejected. Deduct amount: {leave_salary_deduction:.2f} from salary.\n\n"
        "Please process at the next payroll cycle.\n\nRegards,\nHR"
    )
    subject = f"Leave Request Rejection – {employee_name}"
    return {"subject": subject, "body": body}
