import os
from langchain_openai import ChatOpenAI

class Config:
    @staticmethod
    def get_available_models():
        """
        Zwraca tylko GPT-5 (albo cokolwiek podasz w OPENAI_MODEL).
        Domyślnie używa modelu 'gpt-5'. Jeśli nie masz dostępu,
        ustaw w env: OPENAI_MODEL=gpt-4o.
        """
        models = {}
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            model_name = os.getenv("OPENAI_MODEL", "gpt-5")
            try:
                models["openai_gpt5"] = {
                    "name": f"OpenAI ({model_name})",
                    "llm": ChatOpenAI(
                        model=model_name,
                        api_key=openai_key,
                        temperature=0.6,   # trochę niżej dla spójności
                    )
                }
            except Exception as e:
                print(f"⚠️ Błąd inicjalizacji OpenAI: {e}")
        return models

    @staticmethod
    def check_google_search_config():
        from os import getenv
        return bool(getenv("GOOGLE_API_KEY") and getenv("GOOGLE_CX"))
