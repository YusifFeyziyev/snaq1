import os
from dotenv import load_dotenv

load_dotenv()

# GROQ API AÇARLARI
GROQ_KEY_PARSER = os.getenv("GROQ_KEY_PARSER")
GROQ_KEY_M2     = os.getenv("GROQ_KEY_M2")
GROQ_KEY_M3     = os.getenv("GROQ_KEY_M3")
GROQ_KEY_M4     = os.getenv("GROQ_KEY_M4")

# AXTARIŞ API AÇARLARI
TAVILY_KEY  = os.getenv("TAVILY_KEY")
SERPER_KEY  = os.getenv("SERPER_KEY")

# MODEL ADLARI
MODEL_PARSER = "llama-3.3-70b-versatile"
MODEL_M2     = "llama-3.3-70b-versatile"
MODEL_M3     = "llama-3.3-70b-versatile"
MODEL_M4     = "llama-3.3-70b-versatile"
