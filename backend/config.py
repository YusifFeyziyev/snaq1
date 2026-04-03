import os
from dotenv import load_dotenv

load_dotenv()

# ====================== GROQ API AÇARLARI ======================
# Parser üçün bir neçə Groq key-i (fallback ilə)
GROQ_KEYS_PARSER = [
    os.getenv("GROQ_KEY_PARSER_1"),
    os.getenv("GROQ_KEY_PARSER_2"),
    os.getenv("GROQ_KEY_PARSER_3"),
]
# Boş olan key-ləri filter et
GROQ_KEYS_PARSER = [key for key in GROQ_KEYS_PARSER if key]


GROQ_KEY_M3     = os.getenv("GROQ_KEY_M3")
GROQ_KEY_M4     = os.getenv("GROQ_KEY_M4")

# ====================== GEMINI API AÇARI (Yalnız M2 üçün) ======================
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")

# ====================== AXTARIŞ API AÇARLARI ======================
TAVILY_KEY      = os.getenv("TAVILY_KEY")
SERPER_KEY      = os.getenv("SERPER_KEY")

# ====================== MODEL ADLARI ======================
MODEL_PARSER = "llama-3.3-70b-versatile"
MODEL_M2     = "gemini-2.5-flash"          # ← Yalnız M2 Gemini
MODEL_M3     = "llama-3.3-70b-versatile"
MODEL_M4     = "llama-3.3-70b-versatile"