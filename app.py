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
    # USUNIĘTO IMPORT CHECKPOINTÓW - będziemy działać bez zapisywania stanu
    print("✅ Wszystkie moduły zaimportowane pomyślnie")
except ImportError as e:
    st.error(f"Błąd krytyczny: Nie udało się zaimportować modułów. Upewnij się, że wszystkie pliki są na swoich miejscach. Błąd: {e}")
    st.stop()

# --- Interfejs użytkownika ---
st.title("🚀 Turbo Orkiestrator Treści")
st.markdown("Aplikacja do automatycznego generowania artykułów SEO w oparciu o analizę konkurencji i zdefiniowaną personę.")

# --- Pasek boczny do konfiguracji ---
with st.sidebar:
    st.header("🔑 Konfiguracja API")
    st.markdown("Wprowadź swoje klucze API. Na Streamlit Cloud użyj wbudowanych sekretów.")

    def get_secret(key):
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
        return None

    os.environ["OPENAI_API_KEY"] = st.text_input("OpenAI API Key", value=get_secret("OPENAI_API_KEY") or "", type="password")
    os.environ["ANTHROPIC_API_KEY"] = st.text_input("Anthropic API Key", value=get_secret("ANTHROPIC_API_KEY") or "", type="password")
    os.environ["GEMINI_API_KEY"] = st.text_input("Google Gemini API Key", value=get_secret("GEMINI_API_KEY") or "", type="password")
    os.environ["GOOGLE_API_KEY"] = st.text_input("Google Search API Key", value=get_secret("GOOGLE_API_KEY") or "", type="password")
    os.environ["GOOGLE_CX"] = st.text_input("Google Search CX ID", value=get_secret("GOOGLE_CX") or "", type="password")
    
    st.divider()
    st.info("Pamiętaj, aby nigdy nie udostępniać swoich kluczy API publicznie.")
    st.warning("⚠️ W tej wersji aplikacja nie zapisuje stanu między sesjami.")

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

col1, col2 = st.columns(2)

with col1:
    keyword = st.text_input("Słowo kluczowe", placeholder="np. najlepsza karma dla kota")
    selected_persona_name = st.selectbox("Wybierz personę", options=persona_names, index=0 if persona_names else None, help="Styl i ton, w jakim zostanie napisany artykuł.")

with col2:
    website_url = st.text_input("URL do analizy Tone of Voice (opcjonalnie)", placeholder="https://twoja-strona.pl")
    if available_models:
        selected_llm_name = st.selectbox("Wybierz model LLM", options=list(available_models.keys()), format_func=lambda k: available_models[k]['name'], help="Silnik AI, który będzie generował treść.")
    else:
        st.warning("Brak dostępnych modeli LLM. Skonfiguruj klucze API w panelu bocznym.")
        selected_llm_name = None

st.header("2. Uruchom proces")

start_button = st.button("🚀 Generuj Artykuł", type="primary", disabled=not all([keyword, selected_persona_name, selected_llm_name]))

if start_button:
    with st.spinner("Proces w toku... To może potrwać kilka minut."):
        # Budujemy workflow BEZ checkpointera
        workflow_app = build_workflow()

        session_id = f"sesja-{uuid.uuid4()}"
        st.info(f"Rozpoczynam pracę z ID sesji: **{session_id}**")

        initial_state = {
            "llm": available_models[selected_llm_name]["llm"],
            "keyword": keyword,
            "website_url": website_url if website_url else None,
            "persona": personas[selected_persona_name],
        }
        
        st.subheader("Postęp generowania")
        log_container = st.container(height=300)
        st.subheader("Wynik końcowy")
        result_container = st.empty()

        try:
            log_placeholder = log_container.empty()
            all_logs = ""
            final_result = None
            
            # Uruchamiamy workflow
            for result in workflow_app.stream(initial_state, stream_mode="values", recursion_limit=50):
                if result:
                    # Znajdź aktywny węzeł (ostatni klucz w result)
                    if result.keys():
                        active_node = list(result.keys())[-1]
                        log_entry = f"--- Krok zakończony: {active_node} ---\n"
                        all_logs += log_entry
                        log_placeholder.code(all_logs, language="log")
                    
                    # Zapisz ostatni result
                    final_result = result

            # Pobierz final_article z ostatniego resultu
            final_article = final_result.get("final_article") if final_result else None

            with result_container.container(border=True):
                if final_article:
                    st.success("🎉 Artykuł został wygenerowany!")
                    
                    edited_article = st.text_area(
                        "Edytuj wygenerowany artykuł:",
                        value=final_article,
                        height=500,
                        help="Możesz wprowadzić ostateczne poprawki przed pobraniem pliku."
                    )
                    
                    safe_session_id = re.sub(r'[^a-zA-Z0-9_-]', '', session_id)
                    st.download_button(
                        label="Pobierz artykuł (.md)",
                        data=edited_article,
                        file_name=f"artykul_{safe_session_id}.md",
                        mime="text/markdown",
                    )
                else:
                    st.error("Nie udało się wygenerować artykułu. Sprawdź logi powyżej.")
                    if final_result:
                        st.write("Dostępne klucze w ostatnim result:", list(final_result.keys()))
        
        except Exception as e:
            st.error(f"Wystąpił krytyczny błąd: {e}")
            st.exception(e)  # Pokaże pełny stack trace
