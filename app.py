# app.py
import os
import sys
import re
import json
import uuid
import streamlit as st

# --- Konfiguracja strony ---
st.set_page_config(
    page_title="Turbo Orkiestrator Treści — GPT-5 Edition",
    page_icon="🚀",
    layout="wide"
)

# --- LIVE DEBUG: przekierowanie printów do Streamlit ---
class StreamlitPrintCapture:
    def __init__(self):
        self.logs = []
        self.placeholder = None

    def write(self, text):
        if text.strip():
            self.logs.append(text.strip())
            if self.placeholder:
                recent = self.logs[-40:]
                self.placeholder.code("\n".join(recent), language="log")

    def flush(self):
        pass

    def set_placeholder(self, placeholder):
        self.placeholder = placeholder

print_capture = StreamlitPrintCapture()

# --- Ustawienie zmiennych środowiskowych z secrets ---
def setup_environment():
    """
    Pobiera klucze API z st.secrets i ustawia zmienne środowiskowe.
    Zwraca listę brakujących kluczy.
    """
    secrets_keys = [
        "OPENAI_API_KEY",
        "OPENAI_MODEL",      # opcjonalny, ale pobieramy jeśli jest
        "GOOGLE_API_KEY",    # opcjonalny, do SERP CSE
        "GOOGLE_CX"          # opcjonalny, do SERP CSE
    ]
    missing = []
    for key in secrets_keys:
        if hasattr(st, "secrets") and key in st.secrets:
            os.environ[key] = str(st.secrets[key])
        else:
            # OPENAI_API_KEY jest wymagany
            if key == "OPENAI_API_KEY":
                missing.append(key)
    return missing

# --- Środowisko i ścieżki ---
missing_keys = setup_environment()

# Dodaj src do PATH, żeby importy zadziałały niezależnie od uruchomienia
SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# --- Importy logiki backendu ---
try:
    from config import Config
    from graph import build_workflow
except Exception as e:
    st.error(f"Błąd krytyczny importu modułów z katalogu src. Szczegóły: {e}")
    st.stop()

# --- Nagłówek i opis ---
st.title("🚀 Turbo Orkiestrator Treści — GPT-5 Edition")
st.markdown(
    "Jednym strzałem: research → konspekt → artykuł → polish → meta. "
    "Bez zbędnych pętli i zabawy w 'tone of voice z URL'."
)

# --- Weryfikacja kluczy ---
if missing_keys:
    st.error("❌ Brak wymaganych kluczy API w secrets.")
    st.markdown("**Brakujące klucze:**")
    for key in missing_keys:
        st.markdown(f"- `{key}`")
    st.markdown(
        """
        **Jak dodać secrets w Streamlit Cloud:**
        ```
        OPENAI_API_KEY = "sk-..."
        OPENAI_MODEL = "gpt-5"  # opcjonalnie, domyślnie gpt-5
        GOOGLE_API_KEY = "AIza..."  # opcjonalnie
        GOOGLE_CX = "01234..."      # opcjonalnie
        ```
        """
    )
    st.stop()

# --- Wczytanie modeli i person ---
try:
    available_models = Config.get_available_models()
except Exception as e:
    st.error(f"Nie udało się zainicjalizować modeli. Szczegóły: {e}")
    st.stop()

if not available_models:
    st.error("Brak dostępnych modeli LLM. Sprawdź OPENAI_API_KEY i ewentualnie OPENAI_MODEL.")
    st.stop()

try:
    personas_path = os.path.join(SRC_DIR, "personas.json")
    with open(personas_path, "r", encoding="utf-8") as f:
        personas = json.load(f)
    persona_names = list(personas.keys())
    if not persona_names:
        raise ValueError("Plik personas.json jest pusty.")
except Exception as e:
    st.error(f"Błąd wczytywania person z src/personas.json. Szczegóły: {e}")
    personas = {}
    persona_names = []
    st.stop()

# --- UI: parametry wejściowe ---
st.header("1. Parametry artykułu")

col1, col2 = st.columns(2)
with col1:
    keyword = st.text_input("Słowo kluczowe", placeholder="np. najlepsza karma dla kota")
with col2:
    selected_persona_name = st.selectbox("Wybierz personę", options=persona_names, index=0 if persona_names else None)

if selected_persona_name and personas:
    with st.expander("📝 Podgląd persony"):
        persona = personas[selected_persona_name]
        st.markdown(f"**{persona.get('name', selected_persona_name)}**")
        prompt_preview = persona.get("prompt", "")
        st.text(prompt_preview[:800] + ("..." if len(prompt_preview) > 800 else ""))

# --- Start ---
st.header("2. Generowanie")

start_button = st.button(
    "🚀 Generuj artykuł",
    type="primary",
    disabled=not all([keyword, selected_persona_name])
)

if start_button:
    # Przekieruj printy do logów w UI
    original_stdout = sys.stdout
    sys.stdout = print_capture
    try:
        with st.spinner("Lecę po SERPy, czyszczę strony i składam tekst..."):
            st.subheader("🔥 Live Debug")
            live_log_container = st.empty()
            print_capture.set_placeholder(live_log_container)

            # Budowa workflow
            try:
                workflow_app = build_workflow()
                print("✅ Workflow skompilowany")
            except Exception as e:
                st.error(f"Nie udało się skompilować workflow. {e}")
                raise

            # Wybór modelu (pierwszy dostępny)
            model_key = list(available_models.keys())[0]
            llm = available_models[model_key]["llm"]

            # Stan początkowy
            initial_state = {
                "llm": llm,
                "keyword": keyword,
                "persona": personas[selected_persona_name]
            }

            print(f"🧠 Model: {available_models[model_key]['name']}")
            print(f"📝 Keyword: {keyword}")
            print(f"👤 Persona: {personas[selected_persona_name].get('name', selected_persona_name)}")
            print("=" * 60)

            final_state = {}
            step_counter = 0

            for result in workflow_app.stream(initial_state):
                if not result:
                    continue
                # aktualizuj stan i loguj kroki
                final_state.update(result)
                for key in result.keys():
                    step_counter += 1
                    print(f"🔄 Krok #{step_counter}: {key}")

            # --- Wyniki ---
            st.subheader("📄 Artykuł")
            final_article = final_state.get("final_article")
            if final_article:
                st.markdown(final_article, unsafe_allow_html=False)

                safe_kw = re.sub(r"\W+", "_", keyword.lower()).strip("_") or "artykul"
                st.download_button(
                    "📥 Pobierz artykuł .md",
                    data=final_article,
                    file_name=f"artykul_{safe_kw}.md",
                    mime="text/markdown",
                    key=f"dl_md_{uuid.uuid4()}"
                )
            else:
                st.error("Nie powstał finalny artykuł. Sprawdź logi wyżej.")
                st.write("Debug keys:", list(final_state.keys()))
            
            # Meta
            st.subheader("🔧 Meta")
            meta_title = final_state.get("meta_title", "")
            meta_desc = final_state.get("meta_description", "")

            colA, colB = st.columns(2)
            colA.text_input("Meta Title", value=meta_title, key="meta_title_show")
            colB.text_area("Meta Description", value=meta_desc, height=80, key="meta_desc_show")

            # Źródła
            with st.expander("🔗 Źródła z SERP"):
                urls = final_state.get("raw_research_data", {}).get("urls", [])
                if urls:
                    for i, u in enumerate(urls, 1):
                        st.markdown(f"{i}. {u}")
                else:
                    st.write("Brak listy URL. Prawdopodobnie Google CSE nie było skonfigurowane.")

            print("🎉 Proces zakończony.")
    except Exception as e:
        st.error(f"❌ Wystąpił błąd: {e}")
        st.exception(e)
    finally:
        # Przywróć stdout
        sys.stdout = original_stdout

# --- Stopka ---
st.markdown("---")
st.markdown("🚀 **Turbo Orkiestrator Treści — GPT-5 Edition** • Research → Outline → Article → Polish → Meta")
