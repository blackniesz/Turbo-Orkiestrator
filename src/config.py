# Zmodyfikowana zawartość pliku src/config.py

import os
try:
    from google.colab import userdata
    IS_COLAB = True
except ImportError:
    IS_COLAB = False

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

# Jeśli nie jesteśmy w Colab, załaduj zmienne z pliku .env
if not IS_COLAB:
    load_dotenv()

class Config:
    @staticmethod
    def get_api_key(key_name: str) -> str | None:
        """Pobiera klucz API z sekretów Colab lub zmiennych środowiskowych."""
        if IS_COLAB:
            try:
                return userdata.get(key_name)
            except userdata.SecretNotFoundError:
                print(f"⚠️ Ostrzeżenie: Nie znaleziono sekretu '{key_name}' w Google Colab.")
                return None
        return os.getenv(key_name)

    # Używamy nowej funkcji do pobierania kluczy
    API_KEYS = {
        "OPENAI_API_KEY": get_api_key.__func__("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": get_api_key.__func__("ANTHROPIC_API_KEY"),
        "DEEPSEEK_API_KEY": get_api_key.__func__("DEEPSEEK_API_KEY"),
        "GEMINI_API_KEY": get_api_key.__func__("GEMINI_API_KEY"),
        "GROK_API_KEY": get_api_key.__func__("GROK_API_KEY"),
        "GOOGLE_API_KEY": get_api_key.__func__("GOOGLE_API_KEY"),
        "GOOGLE_CX": get_api_key.__func__("GOOGLE_CX"),
    }

    @staticmethod
    def get_available_models():
        models = {}
        if Config.API_KEYS.get("OPENAI_API_KEY"):
            models["openai"] = {
                "name": "OpenAI (GPT-4o)",
                "llm": ChatOpenAI(model="gpt-4o-2024-08-06", api_key=Config.API_KEYS["OPENAI_API_KEY"])
            }
        if Config.API_KEYS.get("ANTHROPIC_API_KEY"):
            models["anthropic"] = {
                "name": "Anthropic (Claude 3.7 Sonnet)",
                "llm": ChatAnthropic(model="claude-3-7-sonnet-20250219", api_key=Config.API_KEYS["ANTHROPIC_API_KEY"])
            }
        # Poprawka dla Gemini - model może wymagać innego klucza niż GOOGLE_API_KEY
        gemini_key = Config.API_KEYS.get("GEMINI_API_KEY") or Config.API_KEYS.get("GOOGLE_API_KEY")
        if gemini_key:
            models["gemini"] = {
                "name": "Google (Gemini 2.5 Flash)",
                "llm": ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=gemini_key)
            }
        if Config.API_KEYS.get("DEEPSEEK_API_KEY"):
            models["deepseek"] = {
                "name": "DeepSeek (deepseek-chat)",
                "llm": ChatOpenAI(model="deepseek-chat", api_key=Config.API_KEYS["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")
            }
        if Config.API_KEYS.get("GROK_API_KEY"):
            models["grok"] = {
                "name": "x.ai (Grok-3)",
                "llm": ChatOpenAI(
                    model="grok-3",
                    api_key=Config.API_KEYS["GROK_API_KEY"],
                    base_url="https://api.x.ai/v1"
                )
            }
        return models

    @staticmethod
    def set_google_env_vars():
        # Ustawiamy zmienne środowiskowe, których używają inne biblioteki (np. googleapiclient)
        google_api_key = Config.API_KEYS.get("GOOGLE_API_KEY")
        google_cx = Config.API_KEYS.get("GOOGLE_CX")
        if google_api_key:
            os.environ["GOOGLE_API_KEY"] = google_api_key
        if google_cx:
            os.environ["GOOGLE_CX"] = google_cx


if __name__ == "__main__":
    # Przykład użycia
    Config.set_google_env_vars()
    available_models = Config.get_available_models()
    print("Dostępne modele LLM:")
    for key, model_info in available_models.items():
        print(f"- {model_info['name']} (klucz: {key})")

    if not Config.API_KEYS.get("OPENAI_API_KEY"):
        print("\nBrak klucza OPENAI_API_KEY.")
    else:
        print("\nOPENAI_API_KEY jest ustawiony.")
