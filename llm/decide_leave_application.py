from langchain_groq import ChatGroq
from langchain.messages import HumanMessage
import json
from datetime import date
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    max_tokens=500
)


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

1. If remaining_leaves <= 0 → REJECT

2. If leave_start or leave_end is missing → PENDING

3. Prior notice rule:
   - If leave starts LESS THAN 3 DAYS from today:
       - Normally REJECT
       - EXCEPTIONS:
         • medical emergency
         • accident
         • family emergency
         • hospitalization
         • serious illness
       - In exceptions → PENDING (not auto-approved)

4. If leave reason is vague, unclear, or casual:
   Examples:
     - birthday
     - party
     - chilling
     - girlfriend / boyfriend event
   → REJECT

5. Senior responsibility rule:
   - If employee_position contains:
       "Lead", "Manager", "Head", "Senior"
   - And leave is sudden + non-emergency
   → REJECT

6. Approval conditions:
   - Proper prior notice (≥ 3 days)
   - Clear reason
   - Remaining leaves available
   → APPROVE

7. If you are unsure at any point → PENDING

--------------------------------
IMPORTANT
--------------------------------
- Do NOT explain your decision.
- Do NOT return JSON.
- Do NOT add punctuation.
- Return ONLY: approved, pending, or rejected.
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    decision = response.content.strip().lower()

    if decision not in {"approved", "pending", "rejected"}:
        return "pending"

    return decision

