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
# 1️⃣ Employee Decision Email (Approved / Pending / Rejected)
# -------------------------
def draft_employee_decision_email(
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
    leave_salary_deduction: float = 0.0,
    prior_notice_days: int | None = None,
    max_retries: int = 3
) -> dict:
    """
    Drafts a polite HR email to the employee for approved / pending / rejected decisions.
    Returns a dict with 'subject' and 'body'.
    If LLM fails to return valid JSON, uses a deterministic fallback email.
    """
    normalized_decision = (leave_decision or "pending").strip().lower()
    if normalized_decision not in {"approved", "pending", "rejected"}:
        normalized_decision = "pending"

    policy_line = "Company policy requires a minimum of 3 calendar days prior notice for planned leave."
    salary_note_rule = (
        "If decision is rejected, include a gentle explanatory note about payroll deduction amount "
        f"({leave_salary_deduction:.2f}) and ask employee to contact HR if they want reconsideration."
    )
    prompt = f"""
You are an HR assistant drafting an email to an employee.

Rules:
- Decision can be approved, pending, or rejected.
- Tone must be polite, supportive, suggestive, and explanatory (NOT harsh).
- Include remaining leaves in the email.
- Reference leave dates and reason.
- Treat this line as fixed policy: "{policy_line}"
- NEVER mention "48 hours". ALWAYS use "3 calendar days prior notice" if short-notice policy is referenced.
- If approved: appreciate timely notice and confirm acceptance.
- If pending: explain request needs admin review and final confirmation will follow.
- If rejected: explain insufficient notice and the policy impact in a respectful way.
- {salary_note_rule}
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

HR Decision: {normalized_decision}
Prior Notice (days): {prior_notice_days}
"""

    for attempt in range(max_retries):
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"⚠️ LLM JSON parse failed (attempt {attempt+1}/{max_retries}). Retrying...")
            sleep(1)  # short delay before retry

    # Fallback if LLM keeps failing
    fallback_subject = f"Leave Request Update: {leave_start} to {leave_end}"
    if normalized_decision == "approved":
        fallback_body = (
            f"Dear {employee_name},\n\n"
            f"Your leave request ({leave_start} to {leave_end}) has been approved.\n"
            f"Reason noted: {leave_reason or 'N/A'}.\n"
            f"You currently have {remaining_leaves} leave(s) remaining.\n\n"
            "Thank you for informing the team in advance.\n\n"
            "Best regards,\nHR Department"
        )
    elif normalized_decision == "rejected":
        fallback_body = (
            f"Dear {employee_name},\n\n"
            f"Thank you for your leave request ({leave_start} to {leave_end}). "
            "At this time, we are unable to approve it because the request was submitted with insufficient prior notice.\n"
            "As per policy, planned leave should be notified at least 3 calendar days in advance.\n"
            f"Estimated payroll impact for this period is {leave_salary_deduction:.2f}.\n"
            "If you would like us to reconsider based on exceptional circumstances, please reply to this email.\n"
            f"You currently have {remaining_leaves} leave(s) remaining.\n\n"
            "Best regards,\nHR Department"
        )
    else:  # pending
        fallback_body = (
            f"Dear {employee_name},\n\n"
            f"Your leave request ({leave_start} to {leave_end}) has been placed in pending status.\n"
            "The request needs a second review by admin/HR before a final decision is made.\n"
            f"Reason noted: {leave_reason or 'N/A'}.\n"
            f"You currently have {remaining_leaves} leave(s) remaining.\n\n"
            "We will share the final update shortly.\n\n"
            "Best regards,\nHR Department"
        )
    return {"subject": fallback_subject, "body": fallback_body}


# Backward-compatible wrapper
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
    prior_notice_days: int | None = None,
    max_retries: int = 3
) -> dict:
    return draft_employee_decision_email(
        employee_name=employee_name,
        employee_position=employee_position,
        employee_salary=employee_salary,
        annual_leaves=annual_leaves,
        remaining_leaves=remaining_leaves,
        leave_category=leave_category,
        leave_reason=leave_reason,
        leave_start=leave_start,
        leave_end=leave_end,
        email_subject=email_subject,
        email_body=email_body,
        leave_decision=leave_decision,
        leave_salary_deduction=leave_salary_deduction,
        prior_notice_days=prior_notice_days,
        max_retries=max_retries,
    )


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
- Use formal, calm, and explanatory tone (not harsh).
- Mention this is policy-based and open for HR re-evaluation if justified.
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
        f"Please note that the leave request submitted by {employee_name} ({employee_position}) "
        f"for {leave_start} to {leave_end} has been rejected as per notice policy.\n"
        f"Recommended payroll adjustment: {leave_salary_deduction:.2f}.\n\n"
        "Please process this in the next payroll cycle. If HR communicates a reconsideration, "
        "we will share an updated instruction.\n\nRegards,\nHR"
    )
    subject = f"Leave Request Rejection – {employee_name}"
    return {"subject": subject, "body": body}


def draft_admin_override_email(
    employee_name: str,
    employee_position: str,
    leave_start: str | None,
    leave_end: str | None,
    leave_reason: str | None,
    old_status: str,
    new_status: str,
    max_retries: int = 3
) -> dict:
    """
    Drafts a polite employee-facing email when admin changes leave status manually.
    """
    normalized_old = (old_status or "").strip().lower()
    normalized_new = (new_status or "").strip().lower()
    prompt = f"""
You are an HR assistant drafting an email to an employee.

Rules:
- Explain that admin completed a manual review and updated a previous leave decision.
- Previous status: {normalized_old}
- Updated status: {normalized_new}
- Keep tone respectful, clear, and supportive.
- If updated status is rejected, include a gentle line that employee can reply for clarification.
- If updated status is approved, include reassurance and appreciation.
- Output ONLY valid JSON with keys "subject" and "body".

Employee:
Name: {employee_name}
Position: {employee_position}

Leave Request:
Start Date: {leave_start}
End Date: {leave_end}
Reason: {leave_reason}
"""
    for attempt in range(max_retries):
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            print(f"⚠️ Override LLM JSON parse failed (attempt {attempt+1}/{max_retries}). Retrying...")
            sleep(1)

    fallback_subject = f"Leave Request Status Updated ({leave_start} to {leave_end})"
    if normalized_new == "approved":
        fallback_body = (
            f"Dear {employee_name},\n\n"
            f"After an additional admin review, your leave request ({leave_start} to {leave_end}) "
            "has been updated to approved.\n"
            f"Reason noted: {leave_reason or 'N/A'}.\n\n"
            "Thank you for your patience.\n\n"
            "Best regards,\nHR Department"
        )
    elif normalized_new == "rejected":
        fallback_body = (
            f"Dear {employee_name},\n\n"
            f"After an additional admin review, your leave request ({leave_start} to {leave_end}) "
            "has been updated to rejected.\n"
            f"Reason noted: {leave_reason or 'N/A'}.\n"
            "If you would like clarification or reconsideration, please reply to this email.\n\n"
            "Best regards,\nHR Department"
        )
    else:
        fallback_body = (
            f"Dear {employee_name},\n\n"
            f"After an additional admin review, your leave request ({leave_start} to {leave_end}) "
            "has been updated and is currently pending.\n"
            "We will share the final decision shortly.\n\n"
            "Best regards,\nHR Department"
        )
    return {"subject": fallback_subject, "body": fallback_body}
