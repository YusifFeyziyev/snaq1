import os
from dotenv import load_dotenv

load_dotenv()

# ====================== GROQ API AÇARLARI ======================
# Parser ucun bir nece Groq key-i (fallback ile)
GROQ_KEYS_PARSER = [
    os.getenv("GROQ_KEY_PARSER_1"),
    os.getenv("GROQ_KEY_PARSER_2"),
    os.getenv("GROQ_KEY_PARSER_3"),
]
# Bos olan key-leri filter et
GROQ_KEYS_PARSER = [key for key in GROQ_KEYS_PARSER if key]
GROQ_KEY_M3     = os.getenv("GROQ_KEY_M3")
GROQ_KEY_M4     = os.getenv("GROQ_KEY_M4")

# ====================== GEMINI API ACARI (Yalniz M2 ucun) ======================
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")

# ====================== AXTARIS API ACARLARI ======================
TAVILY_KEY      = os.getenv("TAVILY_KEY")
SERPER_KEY      = os.getenv("SERPER_KEY")

# ====================== MODEL ADLARI ======================
MODEL_PARSER = "llama-3.3-70b-versatile"
MODEL_M2     = "gemini-2.5-flash"
MODEL_M3     = "llama-3.3-70b-versatile"
MODEL_M4     = "llama-3.3-70b-versatile"