import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

class Config:
    @staticmethod
    def get_available_models():
        """
        Zwraca słownik dostępnych modeli LLM na podstawie 
        zmiennych środowiskowych ustawionych z secrets.
        """
        models = {}
        
        # 1. OpenAI GPT-4o
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
        
        # 2. Anthropic Claude 3.5 Sonnet
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                models["anthropic"] = {
                    "name": "Anthropic (Claude 3.7 Sonnet)",
                    "llm": ChatAnthropic(
                        model="claude-3-7-sonnet-20250219", 
                        api_key=anthropic_key,
                        temperature=0.7
                    )
                }
            except Exception as e:
                print(f"⚠️ Błąd inicjalizacji Anthropic: {e}")
        
        # 3. Google (Gemini 2.5 Flash)
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                models["gemini"] = {
                    "name": "Google (Gemini 2.5 Flash)",
                    "llm": ChatGoogleGenerativeAI(
                        model="gemini-2.5-flash", 
                        google_api_key=gemini_key,
                        temperature=0.7
                    )
                }
            except Exception as e:
                print(f"⚠️ Błąd inicjalizacji Gemini: {e}")
        
        # 4. DeepSeek Chat
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            try:
                models["deepseek"] = {
                    "name": "DeepSeek (deepseek-chat)",
                    "llm": ChatOpenAI(
                        model="deepseek-chat", 
                        api_key=deepseek_key,
                        base_url="https://api.deepseek.com/v1",
                        temperature=0.7
                    )
                }
            except Exception as e:
                print(f"⚠️ Błąd inicjalizacji DeepSeek: {e}")
        
        # 5. x.ai Grok-beta
        grok_key = os.getenv("GROK_API_KEY")
        if grok_key:
            try:
                models["grok"] = {
                    "name": "x.ai (Grok-beta)",
                    "llm": ChatOpenAI(
                        model="grok-beta",
                        api_key=grok_key,
                        base_url="https://api.x.ai/v1",
                        temperature=0.7
                    )
                }
            except Exception as e:
                print(f"⚠️ Błąd inicjalizacji Grok: {e}")
        
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
