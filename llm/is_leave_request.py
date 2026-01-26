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

def is_leave_request(subject: str, body: str) -> bool:
    """
    Determines if an email is a leave request.
    Returns True/False.
    """
    prompt = f"""
Determine if the following email is a leave request.
Reply ONLY with YES or NO.

Subject:
{subject}

Body:
{body}
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content.strip().upper() == "YES"