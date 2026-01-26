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

def extract_leave_metadata(
    email_subject: str,
    email_body: str
) -> dict:
    """
    Extracts leave metadata from an employee's email.
    Resolves relative dates like today / tomorrow.
    Returns:
    {
        leave_reason: str | null,
        leave_start: str | null (YYYY-MM-DD),
        leave_end: str | null (YYYY-MM-DD)
    }
    """

    today = date.today().isoformat()

    prompt = f"""
You are an information extraction assistant.

Today's date is: {today}

Your task is to extract structured leave request data from an email.

DATE HANDLING RULES (IMPORTANT):
- If the email mentions "today", use today's date.
- If the email mentions "tomorrow", use today's date + 1 day.
- If the email mentions a single day (e.g. "I can't come today"),
  treat it as both leave_start and leave_end.
- If a date range is mentioned, extract both start and end.
- Resolve relative dates into exact calendar dates.
- Convert all dates to ISO format: YYYY-MM-DD.

GENERAL RULES:
- Do NOT make HR decisions.
- Do NOT invent dates.
- If a value is truly missing, return null.
- Ignore greetings, signatures, and politeness language.

Email Subject:
{email_subject}

Email Body:
{email_body}

Return ONLY valid JSON in this exact format:

{{
  "leave_reason": string or null,
  "leave_start": string or null,
  "leave_end": string or null
}}
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    return json.loads(response.content.strip())
