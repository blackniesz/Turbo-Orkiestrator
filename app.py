# app.py
import os
import sys
import re
import json
import uuid
import streamlit as st

# --- Konfiguracja strony ---
st.set_page_config(
    page_title="Turbo Orkiestrator Treści - GPT-5 Edition",
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
        "OPENAI_MODEL",      # opcjonalny
        "GOOGLE_API_KEY",    # opcjonalny
        "GOOGLE_CX"          # opcjonalny
    ]
    missing = []
    for key in secrets_keys:
        if hasattr(st, "secrets") and key in st.secrets:
            os.environ[key] = str(st.secrets[key])
        else:
            if key == "OPENAI_API_KEY":
                missing.append(key)
    return missing

# --- Środowisko i ścieżki ---
missing_keys = setup_environment()

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
st.title("🚀 Turbo Orkiestrator Treści - GPT-5 Edition")
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

if "last_run" not in st.session_state:
    st.session_state["last_run"] = {}

start_button = st.button(
    "🚀 Generuj artykuł",
    type="primary",
    disabled=not all([keyword, selected_persona_name])
)

if start_button:
    original_stdout = sys.stdout
    sys.stdout = print_capture
    try:
        with st.spinner("Lecę po SERPy, czyszczę strony i składam tekst..."):
            st.subheader("🔥 Live Debug")
            live_log_container = st.empty()
            print_capture.set_placeholder(live_log_container)

            # Budowa workflow
            workflow_app = build_workflow()
            print("✅ Workflow skompilowany")

            # Wybór modelu
            model_key = list(available_models.keys())[0]
            llm = available_models[model_key]["llm"]

            initial_state = {
                "llm": llm,
                "keyword": keyword,
                "persona": personas[selected_persona_name]
            }

            print(f"🧠 Model: {available_models[model_key]['name']}")
            print(f"📝 Keyword: {keyword}")
            print(f"👤 Persona: {personas[selected_persona_name].get('name', selected_persona_name)}")
            print("=" * 60)

            # UI dla etapów
            ui = {
                "research": st.expander("🕵️ Research", expanded=False),
                "outline": st.expander("📋 Outline", expanded=False),
                "draft": st.expander("✍️ Draft (raw_article)", expanded=False),
                "polish": st.expander("✨ Polish (final_article)", expanded=True),
                "seo": st.expander("🔧 SEO", expanded=False),
                "debug": st.expander("🧯 Debug", expanded=False),
            }

            final_state = {}
            step_counter = 0

            for result in workflow_app.stream(initial_state):
                if not result:
                    continue

                # 1) Rozpakuj wynik z pod-klucza węzła: {"node": {...}}
                if len(result) == 1 and isinstance(next(iter(result.values())), dict):
                    step_name, payload = next(iter(result.items()))
                else:
                    step_name, payload = "unknown", result

                # 2) Aktualizuj stan (już spłaszczony)
                final_state.update(payload)
                st.session_state["last_run"].update(payload)

                # 3) Log
                step_counter += 1
                print(f"🔄 Krok #{step_counter}: {step_name}")

                # 4) RESEARCH
                if any(k in payload for k in ("research_corpus", "research_summary", "raw_research_data")):
                    with ui["research"]:
                        st.markdown("**Podsumowanie:**")
                        st.write(final_state.get("research_summary", "")[:2000])
                        st.markdown("**Źródła:**")
                        for i, u in enumerate(final_state.get("raw_research_data", {}).get("urls", []), 1):
                            st.markdown(f"{i}. {u}")
                        st.markdown("**Fragment korpusu:**")
                        st.code(final_state.get("research_corpus", "")[:3000], language="text")
                        st.download_button(
                            "📥 Pobierz research.json",
                            data=json.dumps({
                                "summary": final_state.get("research_summary", ""),
                                "urls": final_state.get("raw_research_data", {}).get("urls", []),
                                "corpus": final_state.get("research_corpus", "")
                            }, ensure_ascii=False, indent=2),
                            file_name=f"research_{re.sub(r'\\W+','_', keyword.lower())}.json",
                            mime="application/json",
                            key=f"dl_research_{uuid.uuid4()}"
                        )

                # 5) OUTLINE
                if "outline" in payload:
                    with ui["outline"]:
                        st.json(final_state["outline"])
                        st.download_button(
                            "📥 Pobierz outline.json",
                            data=json.dumps(final_state["outline"], ensure_ascii=False, indent=2),
                            file_name=f"outline_{re.sub(r'\\W+','_', keyword.lower())}.json",
                            mime="application/json",
                            key=f"dl_outline_{uuid.uuid4()}"
                        )

                # 6) DRAFT
                if "raw_article" in payload:
                    with ui["draft"]:
                        st.markdown(final_state["raw_article"][:30000])
                        st.download_button(
                            "📥 Pobierz draft.md",
                            data=final_state["raw_article"],
                            file_name=f"draft_{re.sub(r'\\W+','_', keyword.lower())}.md",
                            mime="text/markdown",
                            key=f"dl_draft_{uuid.uuid4()}"
                        )

                # 7) POLISH
                if "final_article" in payload:
                    with ui["polish"]:
                        fa = (final_state.get("final_article") or "").strip()
                        if not fa:
                            fa = final_state.get("raw_article", "")
                            st.warning("Final editor zwrócił pustkę. Pokazuję draft.")
                        st.markdown(fa[:60000])
                        st.download_button(
                            "📥 Pobierz final.md",
                            data=fa,
                            file_name=f"final_{re.sub(r'\\W+','_', keyword.lower())}.md",
                            mime="text/markdown",
                            key=f"dl_final_{uuid.uuid4()}"
                        )

                # 8) SEO
                if any(k in payload for k in ("meta_title", "meta_description")):
                    with ui["seo"]:
                        # fallback: wspiera zarówno spłaszczone jak i zagnieżdżone
                        meta_title = final_state.get("meta_title") or final_state.get("seo_generator", {}).get("meta_title") or ""
                        meta_desc = final_state.get("meta_description") or final_state.get("seo_generator", {}).get("meta_description") or ""
                        st.text_input("Meta Title", value=meta_title, key=f"meta_title_{uuid.uuid4()}")
                        st.text_area("Meta Description", value=meta_desc, height=80, key=f"meta_desc_{uuid.uuid4()}")
                        meta_json = json.dumps({
                            "title": meta_title,
                            "description": meta_desc
                        }, ensure_ascii=False, indent=2)
                        st.download_button(
                            "📥 Pobierz meta.json",
                            data=meta_json,
                            file_name=f"meta_{re.sub(r'\\W+','_', keyword.lower())}.json",
                            mime="application/json",
                            key=f"dl_meta_{uuid.uuid4()}"
                        )

            # --- Po streamie: fallback wyświetlania artykułu ---
            st.subheader("📄 Artykuł")

            # spróbuj spłaszczonego stanu
            final_article_show = (
                final_state.get("final_article")
                or final_state.get("final_editor", {}).get("final_article")
                or ""
            ).strip()

            # jeśli pusto, pokaż draft (obsługa obu wariantów)
            if not final_article_show:
                final_article_show = (
                    final_state.get("raw_article")
                    or final_state.get("full_article_writer", {}).get("raw_article")
                    or ""
                ).strip()

            if final_article_show:
                st.markdown(final_article_show, unsafe_allow_html=False)
                safe_kw = re.sub(r"\W+", "_", keyword.lower()).strip("_") or "artykul"
                st.download_button(
                    "📥 Pobierz artykuł .md",
                    data=final_article_show,
                    file_name=f"artykul_{safe_kw}.md",
                    mime="text/markdown",
                    key=f"dl_full_{uuid.uuid4()}"
                )
            else:
                st.error("Nie powstał finalny artykuł ani draft. Sprawdź zakładkę Debug.")

            # Debug - snapshot stanu
            with ui["debug"]:
                st.markdown("**Klucze final_state:**")
                st.write(list(final_state.keys()))
                st.markdown("**Snapshot last_run (persist w sesji):**")
                st.json(st.session_state["last_run"])

            print("🎉 Proces zakończony.")

    except Exception as e:
        st.error(f"❌ Wystąpił błąd: {e}")
        st.exception(e)
    finally:
        # przywróć stdout zawsze, bo inaczej logi zostaną przekierowane na stałe
        sys.stdout = original_stdout

# --- Stopka ---
st.markdown("---")
st.markdown("🚀 **Turbo Orkiestrator Treści - GPT-5 Edition** • Research → Outline → Article → Polish → Meta")
