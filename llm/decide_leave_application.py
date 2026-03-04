from langchain.messages import HumanMessage
from datetime import date
from .llm import llm
from .parse_utils import parse_choice


def decide_leave_application(
    employee_name: str,
    employee_position: str,
    employee_salary: float,
    annual_leaves: int,
    remaining_leaves: int,
    leave_category: str | None,
    leave_reason: str | None,
    leave_start: str | None,  # YYYY-MM-DD
    leave_end: str | None,    # YYYY-MM-DD
    prior_notice_days: int | None,
    leave_days: int | None,
    email_subject: str,
    email_body: str
) -> str:
    """
    HR decision-maker LLM.
    Returns one of: 'approved', 'pending', 'rejected'
    """

    today = date.today().isoformat()

    prompt = f"""
You are an HR decision-maker responsible for approving, rejecting,
or putting leave requests on pending.

Today’s date: {today}

You MUST return ONLY ONE word:
approved OR pending OR rejected

--------------------------------
EMPLOYEE PROFILE
--------------------------------
Name: {employee_name}
Position: {employee_position}
Salary: {employee_salary}
Annual Leaves: {annual_leaves}
Remaining Leaves: {remaining_leaves}

--------------------------------
LEAVE DETAILS
--------------------------------
Leave Category: {leave_category}
Leave Reason: {leave_reason}
Leave Start Date: {leave_start}
Leave End Date: {leave_end}

--------------------------------
ORIGINAL EMAIL
--------------------------------
Subject: {email_subject}

Body:
{email_body}

--------------------------------
DECISION RULES (STRICT)
--------------------------------

1. If remaining_leaves <= 0 → REJECT.

2. If leave_start or leave_end is missing OR unclear → PENDING.

3. Prior notice policy:
   - Company policy requires minimum 3 calendar days prior notice.
   - Computed prior_notice_days is provided below, trust it over any guess.
   - If prior_notice_days >= 3 and reason is reasonable and leave balance is sufficient -> APPROVE.
   - If prior_notice_days < 3:
       - Emergency-like cases (medical emergency, accident, family emergency,
         hospitalization, serious illness, bereavement) -> PENDING.
       - Non-emergency cases -> REJECT.

4. If leave reason is vague, unclear, or frivolous:
   Examples:
     - birthday
     - party
     - chilling
     - girlfriend / boyfriend event
   -> REJECT.

5. If leave_days > remaining_leaves -> REJECT.

6. If you are unsure at any point -> PENDING.

Computed Context:
- prior_notice_days: {prior_notice_days}
- leave_days: {leave_days}

--------------------------------
IMPORTANT
--------------------------------
- Do NOT explain your decision.
- Do NOT return JSON.
- Do NOT add punctuation.
- Return ONLY: approved, pending, or rejected.
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    return parse_choice(
        response.content,
        allowed={"approved", "pending", "rejected"},
        default="pending",
    )
