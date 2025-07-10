import os
import json
import re
from typing import List
from googleapiclient.discovery import build
from langchain_core.messages import HumanMessage, SystemMessage
from crewai_tools import ScrapeWebsiteTool

from state import ArticleWorkflowState, Section

def extract_json_from_string(text: str) -> str | None:
    """Używa wyrażeń regularnych do znalezienia pierwszego bloku JSON w tekście."""
    match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if match:
        return match.group(0)
    return None

def researcher_node(state: ArticleWorkflowState) -> dict:
    print("--- 🕵️ Agent: Researcher ---")
    llm = state["llm"]
    keyword = state["keyword"]
    
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    google_cx = os.environ.get("GOOGLE_CX")

    if not google_api_key or not google_cx:
        print("⚠️ Brak klucza GOOGLE_API_KEY lub GOOGLE_CX. Pomijam krok researchu w Google.")
        return {"research_summary": "Pominięto research w Google z powodu braku kluczy API.", "raw_research_data": {"urls": [], "scraped_content": []}}

    google_search = build("customsearch", "v1", developerKey=google_api_key)
    scrape_tool = ScrapeWebsiteTool()

    print(f"--- 🕵️ Wyszukiwanie w Google dla: {keyword}... ---")
    try:
        search_results = google_search.cse().list(q=keyword, cx=google_cx, num=5, gl='pl', hl='pl', lr='lang_pl').execute()
        urls = [item["link"] for item in search_results.get("items", [])]
        if not urls: 
            return {"research_summary": "Nie udało się znaleźć wyników w Google.", "raw_research_data": {"urls": [], "scraped_content": []}}
    except Exception as e: 
        return {"research_summary": f"Błąd API Google: {e}", "raw_research_data": {"urls": [], "scraped_content": []}}

    print(f"--- 🕵️ Będę analizować treść z następujących {len(urls)} stron: ---")
    for url in urls:
        print(f"  - {url}")

    scraped_content = []
    for url in urls:
        try:
            content = scrape_tool.run(website_url=url)
            scraped_content.append(f"--- Treść ze strony: {url} ---\n\n{content[:8000]}\n\n")
        except Exception as e:
            print(f"⚠️ Błąd podczas scrapowania {url}: {e}")
            scraped_content.append(f"--- Błąd podczas scrapowania {url}: {e} ---\n\n")

    if not scraped_content: 
        return {"research_summary": "Nie udało się pobrać treści.", "raw_research_data": {"urls": urls, "scraped_content": []}}

    print("--- 🕵️ Analizowanie zebranej treści... ---")
    all_content = "\n".join(scraped_content)
    prompt = f"""Jesteś analitykiem SEO. Na podstawie danych dla słowa kluczowego: {keyword}, przygotuj raport w języku polskim. Treść z konkurencji: {all_content}

ANALIZA MUSI ZAWIERAĆ:
- ANALIZA KONKURENCJI: Główne tematy, struktura.
- BADANIE SŁÓW KLUCZOWYCH: Powiązane słowa, pytania, LSI.
- LUKI W TREŚCI: Czego brakuje, unikalne perspektywy.
- REKOMENDACJE: Optymalna struktura (H1, H2, H3), tematy 'must-have'.

Zaprezentuj wyniki w przejrzystym, strukturalnym formacie."""
    response = llm.invoke([HumanMessage(content=prompt)])
    print("✅ Research zakończony.")
    return {"research_summary": response.content, "raw_research_data": {"urls": urls, "scraped_content": scraped_content}}

def voice_analyst_node(state: ArticleWorkflowState) -> dict:
    # ... (bez zmian)
    print("--- 🎨 Agent: Voice Analyst ---")
    llm = state["llm"]
    website_url = state["website_url"]
    if not website_url: 
        return {"tone_of_voice_guidelines": "Brak URL, używam domyślnego stylu persony."}
    scrape_tool = ScrapeWebsiteTool()
    try:
        scraped_content = scrape_tool.run(website_url=website_url)
        if not scraped_content:
            return {"tone_of_voice_guidelines": "Nie udało się pobrać treści ze strony, używam domyślnego stylu persony."}
    except Exception as e:
        print(f"⚠️ Błąd podczas scrapowania strony Tone of Voice {website_url}: {e}")
        return {"tone_of_voice_guidelines": "Błąd podczas pobierania strony, używam domyślnego stylu persony."}
    prompt = f"""Przeanalizuj tekst i zdefiniuj jego styl komunikacji (Tone of Voice). Opisz w 3-4 punktach kluczowe cechy stylu.
Tekst:
---
{scraped_content[:8000]}
---"""
    response = llm.invoke([HumanMessage(content=prompt)])
    print("✅ Analiza Tone of Voice zakończona.")
    return {"tone_of_voice_guidelines": response.content}

def outline_generator_node(state: ArticleWorkflowState) -> dict:
    # ... (bez zmian, ale z poprawkami do JSON)
    print("\n--- 📋 Agent: Outline Generator ---")
    state["outline_revision_count"] = state.get("outline_revision_count", 0) + 1
    print(f"--- 📋 Tworzę konspekt (Próba #{state['outline_revision_count']}) ---")
    llm = state["llm"]
    prompt = f"""Na podstawie researchu, stwórz konspekt artykułu na temat: {state["keyword"]}.
    **NAJWAŻNIEJSZE:** Konspekt musi być idealnie dopasowany do poniższej persony i stylu komunikacji:
    - **Persona:** {state["persona"]["name"]} ({state["persona"]["prompt"]})
    - **Analiza Stylu (Tone of Voice):** {state["tone_of_voice_guidelines"]}
    - Zaproponuj nagłówki H2, a jeśli to zasadne - również H3.
    **Raport z Researchu:**
    ---
    {state["research_summary"]}
    ---
    """
    if state.get("outline_critique"):
        prompt += f"""\n**POPRAWKI OD KRYTYKA:** Twoja poprzednia wersja konspektu została odrzucona. Uwagi: {state["outline_critique"]}. Stwórz konspekt od nowa, uwzględniając te uwagi."""
    prompt += """\nZaproponuj logiczną strukturę z 4-7 głównymi sekcjami (nagłówkami H2). Twoja odpowiedź MUSI zawierać TYLKO I WYŁĄCZNIE listę w formacie JSON. Przykład: ["Wprowadzenie", "Czym jest X?", "Podsumowanie"]"""
    response = llm.invoke([HumanMessage(content=prompt)])
    raw_response_content = response.content
    try:
        json_str = extract_json_from_string(raw_response_content)
        if not json_str: raise json.JSONDecodeError("Nie znaleziono bloku JSON w odpowiedzi.", raw_response_content, 0)
        outline_list = json.loads(json_str)
        outline_structure = [{"title": title, "draft": None, "critique": None, "is_approved": False, "revision_count": 0} for title in outline_list]
        print(f"✅ Wygenerowano konspekt: {outline_list}")
        return {"outline": outline_structure, "outline_critique": None}
    except json.JSONDecodeError:
        print(f"❌ Błąd: Nie udało się wygenerować konspektu w formacie JSON.")
        print(f"--- SUROWA ODPOWIEDŹ OD LLM ---\n{raw_response_content}\n-----------------------------")
        return {"outline_critique": "Błąd formatowania JSON. Model nie zwrócił poprawnej listy."}

def outline_critic_node(state: ArticleWorkflowState) -> dict:
    # ... (bez zmian, ale z poprawkami do JSON)
    print("--- 🧐 Agent: Outline Critic ---")
    llm = state["llm"]
    prompt = f"""Jesteś surowym strategiem treści. Oceń poniższy konspekt artykułu.
    **Kryteria oceny:**
    1. **Logika i Spójność:** Czy struktura jest logiczna?
    2. **Zgodność z Personą:** Czy tematy pasują do stylu persony {state["persona"]["name"]}?
    3. **Wartość:** Czy ten konspekt zapowiada wartościowy artykuł?
    **Konspekt do oceny:**
    {[s["title"] for s in state["outline"]]}
    **Kontekst:**
    - Persona: {state["persona"]["prompt"]}
    - Research: {state["research_summary"][:1000]}...
    Twoja odpowiedź MUSI zawierać TYLKO I WYŁĄCZNIE obiekt w formacie JSON. Przykład: {{"decision": "APPROVE", "critique": "Konspekt jest logiczny."}}"""
    response = llm.invoke([HumanMessage(content=prompt)])
    raw_response_content = response.content
    try:
        json_str = extract_json_from_string(raw_response_content)
        if not json_str: raise json.JSONDecodeError("Nie znaleziono bloku JSON w odpowiedzi.", raw_response_content, 0)
        critique_json = json.loads(json_str)
        decision = critique_json.get("decision", "REVISE").upper()
        critique = critique_json.get("critique", "Brak uwag.")
        if decision == "APPROVE":
            print(f"--- 👍 Konspekt ZAAKCEPTOWANY. ---")
            return {"outline_critique": None}
        else:
            print(f"--- 👎 Konspekt ODRZUCONY. Uwagi: {critique} ---")
            return {"outline_critique": critique}
    except json.JSONDecodeError:
        print(f"❌ Błąd formatu JSON w odpowiedzi krytyka konspektu.")
        print(f"--- SUROWA ODPOWIEDŹ OD LLM ---\n{raw_response_content}\n-----------------------------")
        return {"outline_critique": "Błąd formatu JSON w odpowiedzi krytyka."}

def section_writer_node(state: ArticleWorkflowState) -> dict:
    # ... (bez zmian)
    print("\n--- ✍️ Agent: Section Writer ---")
    current_section = next((s for s in state["outline"] if not s["is_approved"]), None)
    if not current_section: return {}
    current_section["revision_count"] += 1
    print(f"--- ✍️ Piszę sekcję: {current_section['title']} (Próba #{current_section['revision_count']}) ---")
    llm = state["llm"]
    system_prompt = state["persona"]["prompt"]
    approved_drafts = [s["draft"] for s in state["outline"] if s["is_approved"] and s["draft"]]
    context = "\n\n".join(approved_drafts)
    instruction = f"""Napisz treść dla sekcji: {current_section["title"]}. Temat całego artykułu to: {state["keyword"]}.
Kontekst z poprzednich sekcji:
---
{context[-4000:]}
---
Dodatkowe informacje z researchu:
---
{state["research_summary"]}
---
Każdy śródtytuł musi mieć co najmniej dwa akapity. Jeśli to zasadne, stosuj wypunktowania i pogrubienia - ale nie w nadmiarze. Upewnij się, że tekst jest unikalny i wartościowy, bez powtórzeń."""
    if current_section.get("critique"):
        instruction += f"""\n**POPRAWKI OD KRYTYKA:** Twoja poprzednia wersja tej sekcji została odrzucona. Uwagi: {current_section["critique"]}. Napisz tę sekcję od nowa, uwzględniając te uwagi."""
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=instruction)]
    response = llm.invoke(messages)
    current_section["draft"] = response.content
    return {"outline": state["outline"]}

def section_critic_node(state: ArticleWorkflowState) -> dict:
    # ... (z ulepszoną logiką kontekstu)
    print("--- 🧐 Agent: Section Critic ---")
    current_section_index = -1
    for i, s in enumerate(state["outline"]):
        if s.get("revision_count") > 0 and not s.get("is_approved"):
            current_section_index = i
            break
    if current_section_index == -1: return {}
    current_section = state["outline"][current_section_index]
    print(f"--- 🧐 Ocena sekcji: {current_section['title']} ---")
    llm = state["llm"]
    outline_context = []
    for i, section in enumerate(state["outline"]):
        if i < current_section_index: status = "✅ Ukończono"
        elif i == current_section_index: status = "✍️ TERAZ OCENIASZ TĘ SEKCJĘ"
        else: status = "🔜 Następna w kolejce"
        outline_context.append(f"{i+1}. {section['title']} ({status})")
    outline_context_str = "\n".join(outline_context)
    prompt = f"""Jesteś doświadczonym redaktorem. Twoim zadaniem jest ocena jakości i zgodności z personą fragmentu tekstu w kontekście całego artykułu.
**Struktura całego artykułu (Twoja mapa):**
---
{outline_context_str}
---
**Twoje zadania:**
1.  **Skup się na sekcji oznaczonej jako 'TERAZ OCENIASZ TĘ SEKCJĘ'.** Oceń, czy jej treść jest wartościowa, unikalna i dobrze napisana.
2.  **Sprawdź zgodność z personą:** Czy styl i ton tego konkretnego fragmentu pasują do persony: {state["persona"]["name"]}?
3.  **Oceń w kontekście:** Czy ta sekcja dobrze spełnia swoją rolę w strukturze całego artykułu? Nie krytykuj braku elementów (jak FAQ), jeśli widzisz w konspekcie, że pojawią się one w osobnej, późniejszej sekcji.
Odpowiedz w formacie JSON: {{"decision": "APPROVE", "critique": "Twoje uwagi dotyczące TYLKO i WYŁĄCZNIE ocenianej sekcji."}}.
**Tekst do oceny (sekcja: "{current_section['title']}"):**
---
{current_section["draft"]}
---
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    raw_response_content = response.content
    try:
        json_str = extract_json_from_string(raw_response_content) 
        if not json_str: raise json.JSONDecodeError("Nie znaleziono bloku JSON w odpowiedzi.", raw_response_content, 0)
        critique_json = json.loads(json_str)
        decision = critique_json.get("decision", "REVISE").upper()
        critique = critique_json.get("critique", "Brak uwag.")
        if decision == "APPROVE":
            current_section["is_approved"] = True
            current_section["critique"] = None
            print(f"--- 👍 Sekcja '{current_section['title']}' ZAAKCEPTOWANA. ---")
        else:
            current_section["is_approved"] = False
            current_section["critique"] = critique
            print(f"--- 👎 Sekcja '{current_section['title']}' ODRZUCONA. Uwagi: {critique} ---")
    except json.JSONDecodeError:
        current_section["is_approved"] = False
        current_section["critique"] = "Błąd formatu JSON w odpowiedzi krytyka."
        print(f"❌ Błąd formatu JSON w odpowiedzi krytyka sekcji.")
        print(f"--- SUROWA ODPOWIEDŹ OD LLM ---\n{raw_response_content}\n-----------------------------")
    return {"outline": state["outline"]}

def assembler_node(state: ArticleWorkflowState) -> dict:
    print("--- ⚙️ Agent: Assembler ---")
    # Zmieniono: teraz składamy tylko główną treść artykułu
    article_body = "\n\n".join(f"## {s['title']}\n\n{s['draft']}" for s in state["outline"] if s["is_approved"] and s["draft"])
    print("✅ Główna treść artykułu została złożona.")
    return {"assembled_body": article_body}

# --- NOWY AGENT ---
def introduction_writer_node(state: ArticleWorkflowState) -> dict:
    print("--- ✍️ Agent: Introduction Writer ---")
    llm = state["llm"]
    prompt = f"""Jesteś utalentowanym copywriterem. Twoim zadaniem jest napisanie krótkiego, angażującego wstępu (tzw. "hook") do poniższego artykułu. Wstęp powinien mieć 2-3 akapity i zachęcać do przeczytania całości, nie zdradzając jednak wszystkich informacji.

**Kontekst:**
- Słowo kluczowe: {state["keyword"]}
- Persona: {state["persona"]["name"]} ({state["persona"]["prompt"]})

**Główna treść artykułu (do analizy):**
---
{state["assembled_body"][:4000]}
---

Napisz tylko i wyłącznie treść wstępu, bez żadnych dodatkowych komentarzy.
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    print("✅ Angażujący wstęp został wygenerowany.")
    return {"introduction": response.content}

def final_editor_node(state: ArticleWorkflowState) -> dict:
    print("--- ✏️ Agent: Final Editor ---")
    llm = state["llm"]
    # Zmieniono: teraz składamy i polerujemy całość (wstęp + treść)
    h1_title_prompt = f"""Na podstawie słowa kluczowego "{state["keyword"]}" i persony "{state["persona"]["name"]}", wygeneruj chwytliwy i zoptymalizowany pod SEO nagłówek H1 dla artykułu. Zwróć tylko nagłówek, bez dodatkowych komentarzy."""
    h1_title = state["llm"].invoke([HumanMessage(content=h1_title_prompt)]).content.strip()

    full_article_draft = f"# {h1_title}\n\n{state['introduction']}\n\n{state['assembled_body']}"

    prompt = f"""Jesteś redaktorem końcowym. Twoim zadaniem jest ostatni szlif poniższego, kompletnego artykułu. Popraw błędy gramatyczne i stylistyczne, powtórzenia wyrazów. Upewnij się, że przejścia między wstępem a resztą tekstu są płynne i że całość jest spójna. Sprawdź, czy artykuł jest UX-friendly (zawiera wypunktowania i pogrubienia - ale nie w nadmiarze). Nie zmieniaj sensu ani tonu. Zwróć tylko i wyłącznie finalną, 'wypolerowaną' wersję artykułu.
Artykuł do redakcji:
---
{full_article_draft}
---"""
    response = llm.invoke([HumanMessage(content=prompt)])
    print("✅ Artykuł finalnie zredagowany i gotowy!")
    return {"final_article": response.content}

def should_continue_outlining(state: ArticleWorkflowState) -> str:
    # ... (bez zmian)
    print("--- 🤔 Podejmowanie decyzji po krytyce konspektu... ---")
    if state.get("outline_critique"):
        if state.get("outline_revision_count", 0) >= 3:
            print("--- ⚠️ Osiągnięto limit poprawek dla konspektu. Akceptuję siłą. ---")
            return "start_writing"
        print("--- 👎 Konspekt wymaga poprawek. Wracam do generatora. ---")
        return "revise_outline"
    print("--- 👍 Konspekt zatwierdzony. Przechodzę do pisania sekcji. ---")
    return "start_writing"

def should_continue_writing(state: ArticleWorkflowState) -> str:
    # ... (z ulepszoną logiką)
    print("--- 🤔 Podejmowanie decyzji po krytyce sekcji... ---")
    if all(s.get("is_approved", False) for s in state["outline"]):
        print("--- ✅ Wszystkie sekcje zatwierdzone. Przechodzę do składania artykułu. ---")
        return "assemble_article"
    work_in_progress_section = next((s for s in state["outline"] if not s.get("is_approved")), None)
    if not work_in_progress_section:
        print("--- ‼️ Błąd logiczny: Brak niezatwierdzonych sekcji. Wymuszam składanie. ---")
        return "assemble_article"
    if work_in_progress_section.get("revision_count", 0) >= 3:
        print(f"--- ⚠️ Osiągnięto limit poprawek dla sekcji '{work_in_progress_section['title']}'. Akceptuję siłą. ---")
        work_in_progress_section["is_approved"] = True
        if all(s.get("is_approved", False) for s in state["outline"]):
            print("--- ✅ Wszystkie sekcje zatwierdzone po wymuszonej akceptacji. Przechodzę do składania. ---")
            return "assemble_article"
    print(f"--- ✍️ Kontynuuję pętlę pisania/krytyki. Następny krok dla sekcji: '{work_in_progress_section['title']}'. ---")
    return "write_section"
