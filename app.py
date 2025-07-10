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
    OPENAI_API_KEY = "twoj_klucz_openai"
    ANTHROPIC_API_KEY = "twoj_klucz_anthropic"
    GEMINI_API_KEY = "twoj_klucz_gemini"
    GOOGLE_API_KEY = "twoj_klucz_google"
    GOOGLE_CX = "twoj_cx_id"
    ```
    """)
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
        # Budujemy workflow BEZ checkpointera
        workflow_app = build_workflow()

        session_id = f"sesja-{uuid.uuid4()}"
        st.info(f"🚀 Rozpoczynam pracę z ID sesji: **{session_id}**")

        initial_state = {
            "llm": available_models[selected_llm_name]["llm"],
            "keyword": keyword,
            "website_url": website_url if website_url else None,
            "persona": personas[selected_persona_name],
        }
        
        st.subheader("📊 Postęp generowania")
        log_container = st.container(height=300)
        st.subheader("📄 Wynik końcowy")
        result_container = st.empty()

        try:
            log_placeholder = log_container.empty()
            progress_bar = st.progress(0)
            all_logs = ""
            final_result = None
            
            # Definicja kroków workflow
            workflow_steps = [
                ("researcher", "🕵️ Badanie konkurencji i słów kluczowych"),
                ("voice_analyst", "🎨 Analiza stylu komunikacji (Tone of Voice)"),
                ("outline_generator", "📋 Tworzenie konspektu artykułu"),
                ("outline_critic", "🧐 Ocena jakości konspektu"),
                ("section_writer", "✍️ Pisanie sekcji artykułu"),
                ("section_critic", "📝 Kontrola jakości sekcji"),
                ("assembler", "⚙️ Składanie treści artykułu"),
                ("introduction_writer", "🚀 Tworzenie wstępu"),
                ("final_editor", "✨ Finalne szlifowanie artykułu")
            ]
            
            completed_steps = 0
            
            # Uruchamiamy workflow
            for result in workflow_app.stream(initial_state):
                if result:
                    # W podstawowym trybie streamingu result to cały stan
                    final_result = result
                    
                    # Sprawdź które kroki zostały ukończone na podstawie stanu
                    current_step = "nieznany"
                    
                    # Logika określania aktualnego kroku
                    if result.get("final_article"):
                        current_step = "final_editor"
                        completed_steps = 9
                    elif result.get("introduction"):
                        current_step = "introduction_writer"
                        completed_steps = 8
                    elif result.get("assembled_body"):
                        current_step = "assembler"
                        completed_steps = 7
                    elif result.get("outline") and all(s.get("is_approved", False) for s in result.get("outline", [])):
                        current_step = "section_critic"
                        completed_steps = 6
                    elif result.get("outline") and any(s.get("draft") for s in result.get("outline", [])):
                        current_step = "section_writer"
                        completed_steps = 5
                    elif result.get("outline") and not result.get("outline_critique"):
                        current_step = "outline_critic"
                        completed_steps = 4
                    elif result.get("outline"):
                        current_step = "outline_generator"
                        completed_steps = 3
                    elif result.get("tone_of_voice_guidelines"):
                        current_step = "voice_analyst"
                        completed_steps = 2
                    elif result.get("research_summary"):
                        current_step = "researcher"
                        completed_steps = 1
                    
                    # Znajdź opis kroku
                    step_description = next((desc for name, desc in workflow_steps if name == current_step), current_step)
                    
                    # Aktualizuj logi tylko jeśli to nowy krok
                    if not all_logs or current_step not in all_logs:
                        log_entry = f"[{completed_steps:02d}] ✅ {step_description}\n"
                        all_logs += log_entry
                        log_placeholder.code(all_logs, language="log")
                        
                        # Aktualizuj progress bar
                        progress = min(completed_steps / len(workflow_steps), 1.0)
                        progress_bar.progress(progress)

            # Pobierz final_article z ostatniego resultu
            final_article = final_result.get("final_article") if final_result else None

            with result_container.container(border=True):
                if final_article:
                    st.success("🎉 Artykuł został wygenerowany pomyślnie!")
                    
                    # Pokaż statystyki
                    word_count = len(final_article.split())
                    char_count = len(final_article)
                    st.metric("Liczba słów", word_count)
                    st.metric("Liczba znaków", char_count)
                    
                    edited_article = st.text_area(
                        "✏️ Edytuj wygenerowany artykuł:",
                        value=final_article,
                        height=500,
                        help="Możesz wprowadzić ostateczne poprawki przed pobraniem pliku."
                    )
                    
                    safe_session_id = re.sub(r'[^a-zA-Z0-9_-]', '', session_id)
                    st.download_button(
                        label="📥 Pobierz artykuł (.md)",
                        data=edited_article,
                        file_name=f"artykul_{safe_session_id}.md",
                        mime="text/markdown",
                    )
                else:
                    st.error("❌ Nie udało się wygenerować artykułu. Sprawdź logi powyżej.")
                    if final_result:
                        st.write("🔍 Dostępne klucze w ostatnim result:", list(final_result.keys()))
        
        except Exception as e:
            st.error(f"❌ Wystąpił krytyczny błąd: {e}")
            st.exception(e)  # Pokaże pełny stack trace

# --- Footer ---
st.markdown("---")
st.markdown("🚀 **Turbo Orkiestrator Treści** - Zautomatyzowane generowanie artykułów SEO")
