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

# --- LIVE DEBUG: Przekierowanie printów do Streamlit ---
class StreamlitPrintCapture:
    def __init__(self):
        self.logs = []
        self.placeholder = None
    
    def write(self, text):
        if text.strip():  # Ignoruj puste linie
            self.logs.append(text.strip())
            if self.placeholder:
                # Pokaż ostatnie 20 linii
                recent_logs = self.logs[-20:]
                self.placeholder.code('\n'.join(recent_logs), language='log')
    
    def flush(self):
        pass
    
    def set_placeholder(self, placeholder):
        self.placeholder = placeholder

# Globalny capture
print_capture = StreamlitPrintCapture()

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
    # --- LIVE DEBUG SETUP ---
    # Przekieruj printy do naszego captura
    original_stdout = sys.stdout
    sys.stdout = print_capture
    
    try:
        with st.spinner("Proces w toku... To może potrwać kilka minut."):
            # Kontener na logi na żywo
            st.subheader("🔥 Live Debug - Zobacz co się dzieje!")
            live_log_container = st.empty()
            print_capture.set_placeholder(live_log_container)
            
            # Kontener na szczegóły
            details_expander = st.expander("📊 Szczegóły procesu", expanded=True)
            
            workflow_app = build_workflow()
            
            initial_state = {
                "llm": available_models[selected_llm_name]["llm"],
                "keyword": keyword,
                "website_url": website_url if website_url else None,
                "persona": personas[selected_persona_name],
            }
            
            print(f"🚀 ROZPOCZYNAM GENEROWANIE ARTYKUŁU")
            print(f"📝 Keyword: {keyword}")
            print(f"🤖 Model: {available_models[selected_llm_name]['name']}")
            print(f"👤 Persona: {personas[selected_persona_name]['name']}")
            print("=" * 60)
            
            final_result = None
            step_count = 0
            
            for result in workflow_app.stream(initial_state):
                if result and result.keys():
                    step_count += 1
                    final_result = result
                    
                    # Pokaż co się dzieje w każdym kroku
                    for key in result.keys():
                        print(f"\n🔄 KROK #{step_count}: {key.upper()}")
                        
                        # Szczegółowe info dla każdego kroku
                        with details_expander:
                            if key == "researcher":
                                urls = result.get("raw_research_data", {}).get("urls", [])
                                st.markdown("### 🕵️ Research - Analizowane strony:")
                                for i, url in enumerate(urls, 1):
                                    st.markdown(f"{i}. [{url}]({url})")
                                
                                research = result.get("research_summary", "")
                                if research:
                                    st.markdown("### 📊 Fragment analizy:")
                                    st.text_area("Research", research[:1000], height=150, key=f"research_{step_count}")
                            
                            elif key == "outline_generator":
                                outline = result.get("outline", [])
                                st.markdown("### 📋 Wygenerowany konspekt:")
                                for i, section in enumerate(outline, 1):
                                    st.markdown(f"{i}. **{section.get('title', 'Bez tytułu')}**")
                            
                            elif key == "section_writer":
                                outline = result.get("outline", [])
                                for section in outline:
                                    if section.get("draft") and section.get("revision_count", 0) > 0:
                                        st.markdown(f"### ✍️ Napisana sekcja: {section['title']}")
                                        st.text_area("Treść sekcji", section["draft"][:800], height=200, key=f"section_{section['title']}_{step_count}")
                                        break
                            
                            elif key == "introduction_writer":
                                h1 = result.get("h1_title", "")
                                intro = result.get("introduction", "")
                                if h1:
                                    st.markdown(f"### 📰 Tytuł: {h1}")
                                if intro:
                                    st.markdown("### 🚀 Wstęp:")
                                    st.text_area("Wstęp", intro, height=150, key=f"intro_{step_count}")
                        
                        print(f"✅ Zakończono krok: {key}")
            
            # Wyniki końcowe
            st.subheader("📄 Wynik końcowy")
            
            if final_result:
                final_article = final_result.get("final_article")
                raw_article = final_result.get("raw_article")
                
                if final_article:
                    st.success("🎉 Artykuł został wygenerowany pomyślnie!")
                    
                    # Statystyki
                    if raw_article:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            raw_words = len(raw_article.split())
                            st.metric("📄 Słowa (RAW)", raw_words)
                        with col2:
                            final_words = len(final_article.split())
                            st.metric("✨ Słowa (FINAL)", final_words)
                        with col3:
                            difference = final_words - raw_words
                            st.metric("📈 Zmiana", f"{difference:+d}", delta=difference)
                    
                    # Taby z artykułami
                    if raw_article:
                        tab1, tab2 = st.tabs(["✨ Wersja Finalna", "📄 Wersja RAW"])
                        
                        with tab1:
                            edited_final = st.text_area("✏️ Edytuj finalny artykuł:", value=final_article, height=500, key="final_edit")
                            st.download_button("📥 Pobierz FINAL (.md)", data=edited_final, file_name=f"artykul_FINAL_{keyword.replace(' ', '_')}.md", mime="text/markdown")
                        
                        with tab2:
                            edited_raw = st.text_area("✏️ Edytuj RAW artykuł:", value=raw_article, height=500, key="raw_edit")
                            st.download_button("📥 Pobierz RAW (.md)", data=edited_raw, file_name=f"artykul_RAW_{keyword.replace(' ', '_')}.md", mime="text/markdown")
                else:
                    st.error("❌ Nie udało się wygenerować artykułu.")
            
            print("🎉 PROCES ZAKOŃCZONY!")
            
    except Exception as e:
        st.error(f"❌ Wystąpił błąd: {e}")
        st.exception(e)
    finally:
        # Przywróć normalny stdout
        sys.stdout = original_stdout

# --- Footer ---
st.markdown("---")
st.markdown("🚀 **Turbo Orkiestrator Treści** - Zautomatyzowane generowanie artykułów SEO")
