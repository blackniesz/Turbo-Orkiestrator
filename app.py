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
    from langgraph.checkpoints.sqlite import SqliteSaver
except ImportError as e:
    st.error(f"Błąd krytyczny: Nie udało się zaimportować modułów z folderu 'src'. Upewnij się, że folder 'src' istnieje w tym samym katalogu co plik app.py. Błąd: {e}")
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

    # Używamy st.secrets, jeśli jest dostępne, w przeciwnym razie wracamy do inputów
    os.environ["OPENAI_API_KEY"] = st.text_input("OpenAI API Key", value=get_secret("OPENAI_API_KEY") or "", type="password")
    os.environ["ANTHROPIC_API_KEY"] = st.text_input("Anthropic API Key", value=get_secret("ANTHROPIC_API_KEY") or "", type="password")
    os.environ["GEMINI_API_KEY"] = st.text_input("Google Gemini API Key", value=get_secret("GEMINI_API_KEY") or "", type="password")
    os.environ["GOOGLE_API_KEY"] = st.text_input("Google Search API Key", value=get_secret("GOOGLE_API_KEY") or "", type="password")
    os.environ["GOOGLE_CX"] = st.text_input("Google Search CX ID", value=get_secret("GOOGLE_CX") or "", type="password")
    
    st.divider()
    st.info("Pamiętaj, aby nigdy nie udostępniać swoich kluczy API publicznie.")

# --- Główny interfejs ---
st.header("1. Zdefiniuj parametry artykułu")

# Wczytanie dostępnych modeli i person
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

session_id_input = st.text_input("ID Sesji (pozostaw puste, aby stworzyć nową)", help="Podaj to samo ID, aby wznowić przerwany proces generowania.")

start_button = st.button("🚀 Generuj Artykuł", type="primary", disabled=not all([keyword, selected_persona_name, selected_llm_name]))

# --- Logika backendu po naciśnięciu przycisku ---
if start_button:
    with st.spinner("Proces w toku... To może potrwać kilka minut."):
        # Ustawienie checkpointów
        memory = SqliteSaver.from_conn_string("checkpoints.sqlite")
        workflow_app = build_workflow(checkpointer=memory)

        # Konfiguracja sesji
        session_id = session_id_input if session_id_input else f"sesja-{uuid.uuid4()}"
        st.info(f"Rozpoczynam pracę z ID sesji: **{session_id}**")
        config = {"configurable": {"thread_id": session_id}}

        # Sprawdzenie, czy stan już istnieje
        existing_state = workflow_app.get_state(config)
        if existing_state and existing_state.values() and existing_state.values()['llm']:
             st.success("✅ Znaleziono zapisany stan. Wznawiam pracę od ostatniego kroku.")
             initial_state = None
        else:
            st.info("🆕 Tworzę nowy stan początkowy.")
            initial_state = {
                "llm": available_models[selected_llm_name]["llm"],
                "keyword": keyword,
                "website_url": website_url if website_url else None,
                "persona": personas[selected_persona_name],
            }
        
        # Miejsca na dynamiczne wyświetlanie logów i wyniku
        st.subheader("Postęp generowania")
        log_container = st.container(height=300)
        st.subheader("Wynik końcowy")
        result_container = st.empty()

        try:
            log_placeholder = log_container.empty()
            all_logs = ""
            # Uruchomienie procesu z przechwytywaniem logów
            for result in workflow_app.stream(initial_state, config, stream_mode="values", recursion_limit=50):
                active_node = list(result.keys())[0]
                with st_capture(lambda val: None) as captured_output:
                     print(f"--- Krok zakończony: {active_node} ---")
                all_logs += captured_output.getvalue() + "\n"
                log_placeholder.code(all_logs, language="log")

            # Pobranie finalnego stanu i wyświetlenie wyniku
            final_state = workflow_app.get_state(config)
            final_article = final_state.values().get("final_article")

            with result_container.container(border=True):
                if final_article:
                    st.success("🎉 Artykuł został wygenerowany!")
                    
                    # --- NOWY ELEMENT: EDYTOR TEKSTU ---
                    edited_article = st.text_area(
                        "Edytuj wygenerowany artykuł:",
                        value=final_article,
                        height=500,
                        help="Możesz wprowadzić ostateczne poprawki przed pobraniem pliku."
                    )
                    
                    # Opcja pobrania ze zmodyfikowaną treścią
                    safe_session_id = re.sub(r'[^a-zA-Z0-9_-]', '', session_id)
                    st.download_button(
                        label="Pobierz artykuł (.md)",
                        data=edited_article, # Pobieramy treść z edytora
                        file_name=f"artykul_{safe_session_id}.md",
                        mime="text/markdown",
                    )
                else:
                    st.error("Nie udało się wygenerować artykułu. Sprawdź logi powyżej.")
        
        except Exception as e:
            st.error(f"Wystąpił krytyczny błąd: {e}")
            st.warning(f"Proces został przerwany, ale jego stan został zapisany pod ID sesji: **{session_id}**. Aby wznowić, uruchom ponownie z tym samym ID.")
