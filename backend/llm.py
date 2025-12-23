import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

def get_llm(temperature: float = 0.3) -> ChatGroq:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set. Add it to .env")
    return ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name=GROQ_MODEL,
        temperature=temperature,
    )
