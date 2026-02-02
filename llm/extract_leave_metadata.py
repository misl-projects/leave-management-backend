from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.messages import HumanMessage
import json
from datetime import date
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    max_tokens=1000
)

LEAVE_CATEGORIES = [
    "Sick",
    "Casual",
    "Annual"
]

LEAVE_REASONS = [
    "Medical",
    "Accident",
    "Family",
    "Personal",
    "Bereavement",
    "Travel",
    "Maternity",
    "Paternity",
    "Miscellaneous"
]

def extract_leave_metadata(
    email_subject: str,
    email_body: str
) -> dict:
    """
    Extracts leave metadata from an employee's email.
    Resolves relative dates like today / tomorrow.
    Returns both leave_category and leave_reason.
    """

    today = date.today().isoformat()

    prompt = f"""
You are an information extraction assistant.

Today's date is: {today}

Your task is to extract structured leave request data from an email.

DATE HANDLING RULES:
- "today" → today's date
- "tomorrow" → today's date + 1 day
- Single day → both leave_start and leave_end
- Date ranges → extract start and end
- Convert all dates to ISO format YYYY-MM-DD

LEAVE CATEGORY RULES:
- leave_category MUST be one of:
{', '.join(LEAVE_CATEGORIES)}
- Choose based on company policy and intent:
  - Health-related → Sick
  - Short personal needs → Casual
  - Planned vacation / long leave → Annual
- Do NOT invent categories.

LEAVE REASON RULES:
- leave_reason MUST be one of:
{', '.join(LEAVE_REASONS)}
- Choose the closest matching reason from the email.
- Do NOT invent reasons.
- If unclear, use Miscellaneous.

Email Subject:
{email_subject}

Email Body:
{email_body}

Return ONLY valid JSON in this exact format:

{{
  "leave_category": string or null,
  "leave_reason": string or null,
  "leave_start": string or null,
  "leave_end": string or null
}}
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    return json.loads(response.content.strip())
