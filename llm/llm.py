from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

load_dotenv()

_temperature = 0
_max_tokens = 1000

groq_llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=_temperature,
    max_tokens=_max_tokens,
)

gemini_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=_temperature,
    max_output_tokens=_max_tokens,
)

llm = gemini_llm
# llm = groq_llm

if __name__ == "__main__":
    print(llm.invoke("Reply with exactly: ready"))
