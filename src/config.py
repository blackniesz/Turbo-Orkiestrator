import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

class Config:
    @staticmethod
    def get_available_models():
        """
        Zwraca słownik dostępnych modeli LLM na podstawie 
        zmiennych środowiskowych ustawionych z secrets.
        """
        models = {}
        
        # OpenAI GPT-4
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                models["openai"] = {
                    "name": "OpenAI (GPT-4o)",
                    "llm": ChatOpenAI(
                        model="gpt-4o-2024-08-06", 
                        api_key=openai_key,
                        temperature=0.7
                    )
                }
            except Exception as e:
                print(f"⚠️ Błąd inicjalizacji OpenAI: {e}")
        
        # Anthropic Claude
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                models["anthropic"] = {
                    "name": "Anthropic (Claude 3.5 Sonnet)",
                    "llm": ChatAnthropic(
                        model="claude-3-5-sonnet-20241022", 
                        api_key=anthropic_key,
                        temperature=0.7
                    )
                }
            except Exception as e:
                print(f"⚠️ Błąd inicjalizacji Anthropic: {e}")
        
        # Google Gemini
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                models["gemini"] = {
                    "name": "Google (Gemini 1.5 Flash)",
                    "llm": ChatGoogleGenerativeAI(
                        model="gemini-1.5-flash", 
                        google_api_key=gemini_key,
                        temperature=0.7
                    )
                }
            except Exception as e:
                print(f"⚠️ Błąd inicjalizacji Gemini: {e}")
        
        return models

    @staticmethod
    def check_google_search_config():
        """Sprawdza czy Google Search API jest skonfigurowane."""
        google_api_key = os.getenv("GOOGLE_API_KEY")
        google_cx = os.getenv("GOOGLE_CX")
        return bool(google_api_key and google_cx)

if __name__ == "__main__":
    # Test konfiguracji
    available_models = Config.get_available_models()
    print("Dostępne modele LLM:")
    for key, model_info in available_models.items():
        print(f"- {model_info['name']} (klucz: {key})")
    
    if Config.check_google_search_config():
        print("\n✅ Google Search API jest skonfigurowane.")
    else:
        print("\n❌ Google Search API nie jest skonfigurowane.")
