from langchain.messages import HumanMessage
from .llm import llm
from .parse_utils import parse_choice

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
    decision = parse_choice(response.content, allowed={"yes", "no"}, default="no")
    return decision == "yes"
