import streamlit as st
import os
import json
import re
import uuid
import sys
from datetime import datetime
from contextlib import contextmanager
from io import StringIO

# --- Konfiguracja strony ---
st.set_page_config(
    page_title="Turbo Orkiestrator Treści",
    page_icon="🚀",
    layout="wide"
)

# --- Ustawienie zmiennych środowiskowych z secrets ---
def setup_environment():
    """Pobiera klucze API z secrets Streamlit i ustawia zmienne środowiskowe."""
    secrets_keys = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", 
        "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY",
        "GROK_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_CX"
    ]
    
    missing_keys = []
    
    for key in secrets_keys:
        if hasattr(st, 'secrets') and key in st.secrets:
            os.environ[key] = st.secrets[key]
        else:
            missing_keys.append(key)
    
    return missing_keys

# Konfiguracja środowiska
missing_keys = setup_environment()

# --- Przekierowanie stdout do interfejsu Streamlit ---
@contextmanager
def st_capture(output_func):
    """Kontekst do przechwytywania print() i wyświetlania w Streamlit."""
    with StringIO() as stdout, st.chat_message('assistant', avatar="🤖"):
        old_stdout = sys.stdout
        sys.stdout = stdout
        try:
            yield
        finally:
            output_func(stdout.getvalue())
            sys.stdout = old_stdout

# --- Importy z logiki backendu ---
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from config import Config
    from state import ArticleWorkflowState
    from graph import build_workflow
    print("✅ Wszystkie moduły zaimportowane pomyślnie")
except ImportError as e:
    st.error(f"Błąd krytyczny: Nie udało się zaimportować modułów. Upewnij się, że wszystkie pliki są na swoich miejscach. Błąd: {e}")
    st.stop()

# --- Interfejs użytkownika ---
st.title("🚀 Turbo Orkiestrator Treści")
st.markdown("Aplikacja do automatycznego generowania artykułów SEO w oparciu o analizę konkurencji i zdefiniowaną personę.")

# --- Sprawdzenie konfiguracji ---
if missing_keys:
    st.error("❌ **Brak wymaganych kluczy API w secrets!**")
    st.markdown("**Brakujące klucze:**")
    for key in missing_keys:
        st.markdown(f"- `{key}`")
    
    st.markdown("""
    **Jak dodać secrets w Streamlit Cloud:**
    1. Idź do ustawień swojej aplikacji
    2. Znajdź sekcję "Secrets"
    3. Dodaj klucze w formacie:
    ```toml
    OPENAI_API_KEY = "sk-..."
    ANTHROPIC_API_KEY = "sk-ant-..."
    GEMINI_API_KEY = "AIza..."
    DEEPSEEK_API_KEY = "sk-..."
    GROK_API_KEY = "xai-..."
    GOOGLE_API_KEY = "AIza..."
    GOOGLE_CX = "01234..."
    ```
    """)
    st.info("💡 **Tip:** Nie musisz mieć wszystkich kluczy - aplikacja będzie pokazywać tylko dostępne modele!")
    st.stop()

st.success("✅ Wszystkie wymagane klucze API zostały skonfigurowane!")

# --- Główny interfejs ---
st.header("1. Zdefiniuj parametry artykułu")

try:
    available_models = Config.get_available_models()
    with open("src/personas.json", "r", encoding="utf-8") as f:
        personas = json.load(f)
    persona_names = list(personas.keys())
except Exception as e:
    st.error(f"Błąd wczytywania konfiguracji (modele lub persony): {e}")
    available_models, personas, persona_names = {}, {}, []

if not available_models:
    st.warning("⚠️ Brak dostępnych modeli LLM. Sprawdź czy klucze API w secrets są prawidłowe.")
    st.stop()

col1, col2 = st.columns(2)

with col1:
    keyword = st.text_input("Słowo kluczowe", placeholder="np. najlepsza karma dla kota")
    selected_persona_name = st.selectbox(
        "Wybierz personę", 
        options=persona_names, 
        index=0 if persona_names else None, 
        help="Styl i ton, w jakim zostanie napisany artykuł."
    )

with col2:
    website_url = st.text_input(
        "URL do analizy Tone of Voice (opcjonalnie)", 
        placeholder="https://twoja-strona.pl"
    )
    selected_llm_name = st.selectbox(
        "Wybierz model LLM", 
        options=list(available_models.keys()), 
        format_func=lambda k: available_models[k]['name'], 
        help="Silnik AI, który będzie generował treść."
    )

# Pokaż opis wybranej persony
if selected_persona_name and personas:
    with st.expander("📝 Podgląd wybranej persony"):
        persona = personas[selected_persona_name]
        st.markdown(f"**{persona['name']}**")
        st.text(persona['prompt'][:500] + "..." if len(persona['prompt']) > 500 else persona['prompt'])

st.header("2. Uruchom proces")

start_button = st.button(
    "🚀 Generuj Artykuł", 
    type="primary", 
    disabled=not all([keyword, selected_persona_name, selected_llm_name])
)

if start_button:
    with st.spinner("Proces w toku... To może potrwać kilka minut."):
        workflow_app = build_workflow()
        
        initial_state = {
            "llm": available_models[selected_llm_name]["llm"],
            "keyword": keyword,
            "website_url": website_url if website_url else None,
            "persona": personas[selected_persona_name],
        }
        
        st.write("🚀 **LIVE TEST**")
        st.write(f"Keyword: {keyword}")
        st.write(f"Model: {selected_llm_name}")
        st.write(f"Persona: {selected_persona_name}")
        
        # Test z timeoutem
        import time
        start_time = time.time()
        
        try:
            st.write("⏱️ Uruchamiam workflow...")
            step_count = 0
            
            for result in workflow_app.stream(initial_state):
                step_count += 1
                elapsed = time.time() - start_time
                
                st.write(f"📦 Krok #{step_count} po {elapsed:.1f}s: {list(result.keys()) if result else 'None'}")
                
                # Zatrzymaj po 30 sekundach dla testu
                if elapsed > 30:
                    st.warning("⏰ Test zatrzymany po 30s")
                    break
                    
                # Zatrzymaj po 5 krokach dla testu
                if step_count >= 5:
                    st.success("✅ Test zakończony po 5 krokach")
                    break
                    
        except Exception as e:
            st.error(f"❌ Błąd: {e}")
            st.exception(e)

# --- Footer ---
st.markdown("---")
st.markdown("🚀 **Turbo Orkiestrator Treści** - Zautomatyzowane generowanie artykułów SEO")
