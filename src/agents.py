import os
import json
import re
from typing import List
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from langchain_core.messages import HumanMessage, SystemMessage

from state import ArticleWorkflowState, Section

def researcher_node(state: ArticleWorkflowState) -> dict:
    print("🕵️ === ROZPOCZYNAM BADANIE KONKURENCJI ===")
    llm = state["llm"]  # Używamy głównego modelu (na razie bez DeepSeek-R1)
# --- NOWA, NIEZAWODNA FUNKCJA DO SCRAPOWANIA STRON ---
def scrape_website(url: str) -> str:
    """
    Pobiera i wyodrębnia główną treść tekstową z podanego adresu URL.
    Zastępuje zewnętrzną, niestabilną bibliotekę.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # Zgłasza błąd dla kodów 4xx/5xx

        soup = BeautifulSoup(response.content, 'html.parser')

        # Usuwa niepotrzebne elementy (skrypty, style, menu, stopki)
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()

        # Pobiera tekst i czyści go z nadmiarowych białych znaków
        text = soup.get_text(separator=' ', strip=True)
        # Zamienia wielokrotne spacje na pojedyncze
        text = re.sub(r'\s+', ' ', text)
        
        return text
    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas pobierania URL {url}: {e}")
        return f"Błąd podczas pobierania treści z {url}"
    except Exception as e:
        print(f"Nieoczekiwany błąd podczas scrapowania {url}: {e}")
        return f"Nieoczekiwany błąd podczas przetwarzania {url}"


def extract_json_from_string(text: str) -> str | None:
    """Używa wyrażeń regularnych do znalezienia pierwszego bloku JSON w tekście."""
    match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
    if match:
        return match.group(0)
    return None
def researcher_node(state: ArticleWorkflowState) -> dict:
    print("🕵️ === ROZPOCZYNAM BADANIE KONKURENCJI ===")
    llm = state["llm"]  # Używamy głównego modelu (na razie bez DeepSeek-R1)
    keyword = state["keyword"]
    
    google_api_key = os.environ.get("GOOGLE_API_KEY")
    google_cx = os.environ.get("GOOGLE_CX")

    if not google_api_key or not google_cx:
        print("⚠️ Brak klucza GOOGLE_API_KEY lub GOOGLE_CX. Pomijam krok researchu w Google.")
        return {"research_summary": "Pominięto research w Google z powodu braku kluczy API.", "raw_research_data": {"urls": [], "scraped_content": []}}

    google_search = build("customsearch", "v1", developerKey=google_api_key)
    
    print(f"🔍 Wyszukuję w Google: '{keyword}'...")
    try:
        search_results = google_search.cse().list(q=keyword, cx=google_cx, num=5, gl='pl', hl='pl', lr='lang_pl').execute()
        urls = [item["link"] for item in search_results.get("items", [])]
        if not urls: 
            return {"research_summary": "Nie udało się znaleźć wyników w Google.", "raw_research_data": {"urls": [], "scraped_content": []}}
    except Exception as e: 
        return {"research_summary": f"Błąd API Google: {e}", "raw_research_data": {"urls": [], "scraped_content": []}}

    print(f"📋 Znaleziono {len(urls)} stron do analizy:")
    for i, url in enumerate(urls, 1):
        print(f"   {i}. {url}")

    scraped_content = []
    for i, url in enumerate(urls, 1):
        print(f"📄 Analizuję stronę {i}/{len(urls)}: {url[:50]}...")
        content = scrape_website(url)
        scraped_content.append(f"--- Treść ze strony: {url} ---\n\n{content[:8000]}\n\n")

    if not scraped_content: 
        return {"research_summary": "Nie udało się pobrać treści.", "raw_research_data": {"urls": urls, "scraped_content": []}}

    print("🤖 Analizuję zebraną treść za pomocą AI...")
    all_content = "\n".join(scraped_content)
    
    prompt = f"""Jesteś analitykiem SEO. Na podstawie danych dla słowa kluczowego: {keyword}, przygotuj raport w języku polskim. Treść z konkurencji: {all_content}

ANALIZA MUSI ZAWIERAĆ:
- ANALIZA KONKURENCJI: Główne tematy, struktura.
- BADANIE SŁÓW KLUCZOWYCH: Powiązane słowa, pytania, LSI.
- LUKI W TREŚCI: Czego brakuje, unikalne perspektywy.
- REKOMENDACJE: Optymalna struktura (H1, H2, H3), tematy 'must-have'.

Zaprezentuj wyniki w przejrzystym, strukturalnym formacie."""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    print("📊 FRAGMENT RAPORTU Z RESEARCHU:")
    print(f"   {response.content[:300]}...")
    print("✅ Research zakończony!")
    return {"research_summary": response.content, "raw_research_data": {"urls": urls, "scraped_content": scraped_content}}

def voice_analyst_node(state: ArticleWorkflowState) -> dict:
    print("🎨 === ANALIZUJĘ TONE OF VOICE ===")
    llm = state["llm"]
    website_url = state["website_url"]
    
    if not website_url: 
        print("ℹ️ Brak URL, używam domyślnego stylu persony.")
        return {"tone_of_voice_guidelines": "Brak URL, używam domyślnego stylu persony."}
    
    print(f"🌐 Pobieram treść ze strony: {website_url}")
    scraped_content = scrape_website(website_url)
    if "Błąd podczas pobierania" in scraped_content or not scraped_content:
        print(f"⚠️ Nie udało się pobrać treści ze strony: {website_url}")
        return {"tone_of_voice_guidelines": "Nie udało się pobrać treści ze strony, używam domyślnego stylu persony."}

    print("🤖 Analizuję styl komunikacji...")
    prompt = f"""Przeanalizuj tekst i zdefiniuj jego styl komunikacji (Tone of Voice). Opisz w 3-4 punktach kluczowe cechy stylu.

Tekst:
---
{scraped_content[:8000]}
---"""
    response = llm.invoke([HumanMessage(content=prompt)])
    print("📝 WYNIKI ANALIZY TONE OF VOICE:")
    print(f"   {response.content[:200]}...")
    print("✅ Analiza Tone of Voice zakończona!")
    return {"tone_of_voice_guidelines": response.content}

def outline_generator_node(state: ArticleWorkflowState) -> dict:
    print("📋 === TWORZĘ KONSPEKT ARTYKUŁU ===")
    state["outline_revision_count"] = state.get("outline_revision_count", 0) + 1
    print(f"📝 Próba #{state['outline_revision_count']}")
    llm = state["llm"]

    prompt = f"""Na podstawie researchu, stwórz konspekt artykułu na temat: {state["keyword"]}.

    **NAJWAŻNIEJSZE:** Konspekt musi być idealnie dopasowany do poniższej persony i stylu komunikacji:
    - **Persona:** {state["persona"]["name"]} ({state["persona"]["prompt"]})
    - **Analiza Stylu (Tone of Voice):** {state["tone_of_voice_guidelines"]}
    - Wszystkie nagłówki zapisuj w sposób naturalny, jak w zdaniu.
    - Zaproponuj nagłówki H2, a jeśli to zasadne - również H3.

    **Raport z Researchu:**
    ---
    {state["research_summary"]}
    ---
    """
    if state.get("outline_critique"):
        prompt += f"""\n
        **POPRAWKI OD KRYTYKA:** Twoja poprzednia wersja konspektu została odrzucona.
        Uwagi: {state["outline_critique"]}
        Stwórz konspekt od nowa, uwzględniając te uwagi.
        """
        print(f"🔄 Poprawiam konspekt na podstawie uwag: {state['outline_critique'][:100]}...")
    
    prompt += """\n
    Zaproponuj logiczną strukturę z 4-7 głównymi sekcjami (nagłówkami H2). 
    Twoja odpowiedź MUSI zawierać TYLKO I WYŁĄCZNIE listę w formacie JSON.
    Przykład poprawnej odpowiedzi: ["Wprowadzenie", "Czym jest X?", "Główne zalety Y", "Podsumowanie"]
    Nie dodawaj żadnych wyjaśnień, komentarzy ani bloków kodu markdown. Zwróć czysty tekst JSON.
    """

    print("🤖 Generuję konspekt...")
    response = llm.invoke([HumanMessage(content=prompt)])
    raw_response_content = response.content

    try:
        json_str = extract_json_from_string(raw_response_content)
        if not json_str:
            raise json.JSONDecodeError("Nie znaleziono bloku JSON w odpowiedzi.", raw_response_content, 0)

        outline_list = json.loads(json_str)
        outline_structure = [{"title": title, "draft": None, "critique": None, "is_approved": False, "revision_count": 0} for title in outline_list]
        print("📋 WYGENEROWANY KONSPEKT:")
        for i, title in enumerate(outline_list, 1):
            print(f"   {i}. {title}")
        print("✅ Konspekt wygenerowany!")
        return {"outline": outline_structure, "outline_critique": None}
    except json.JSONDecodeError:
        print(f"❌ Błąd: Nie udało się wygenerować konspektu w formacie JSON.")
        print(f"📄 Surowa odpowiedź: {raw_response_content[:200]}...")
        return {"outline_critique": "Błąd formatowania JSON. Model nie zwrócił poprawnej listy. Proszę spróbować ponownie."}

def outline_critic_node(state: ArticleWorkflowState) -> dict:
    print("🧐 === OCENIAM KONSPEKT ===")
    llm = state["llm"]
    
    konspekt_lista = [s["title"] for s in state["outline"]]
    print("📋 Oceniam konspekt:")
    for i, title in enumerate(konspekt_lista, 1):
        print(f"   {i}. {title}")
    
    prompt = f"""Jesteś surowym strategiem treści. Oceń poniższy konspekt artykułu.

    **Kryteria oceny:**
    1. **Logika i Spójność:** Czy struktura jest logiczna i prowadzi czytelnika od A do Z?
    2. **Zgodność z Personą:** Czy tematy sekcji pasują do stylu i wiedzy persony {state["persona"]["name"]}?
    3. **Wartość:** Czy ten konspekt zapowiada artykuł, który będzie wartościowy i wyróżni się na tle konkurencji (na podstawie researchu)?
    4. **SEO:** Czy konspekt uwzględnia kluczowe aspekty SEO z raportu researchu?

    **Konspekt do oceny:**
    {konspekt_lista}

    **Kontekst:**
    - Persona: {state["persona"]["prompt"]}
    - Research: {state["research_summary"][:1000]}...

    Twoja odpowiedź MUSI zawierać TYLKO I WYŁĄCZNIE obiekt w formacie JSON.
    Przykład: {{"decision": "APPROVE", "critique": "Konspekt jest logiczny i zgodny z wytycznymi."}}
    """
    
    print("🤖 Oceniam jakość konspektu...")
    response = llm.invoke([HumanMessage(content=prompt)])
    raw_response_content = response.content
    try:
        json_str = extract_json_from_string(raw_response_content)
        if not json_str:
            raise json.JSONDecodeError("Nie znaleziono bloku JSON w odpowiedzi.", raw_response_content, 0)
        
        critique_json = json.loads(json_str)
        decision = critique_json.get("decision", "REVISE").upper()
        critique = critique_json.get("critique", "Brak uwag.")
        
        if decision == "APPROVE":
            print("👍 KONSPEKT ZAAKCEPTOWANY!")
            print(f"💬 Komentarz: {critique}")
            return {"outline_critique": None}
        else:
            print("👎 KONSPEKT ODRZUCONY!")
            print(f"💬 Uwagi: {critique}")
            return {"outline_critique": critique}
    except json.JSONDecodeError:
        print(f"❌ Błąd formatu JSON w odpowiedzi krytyka.")
        print(f"📄 Surowa odpowiedź: {raw_response_content[:200]}...")
        return {"outline_critique": "Błąd formatu JSON w odpowiedzi krytyka. Proszę spróbować ponownie."}

def section_writer_node(state: ArticleWorkflowState) -> dict:
    print("✍️ === PISZĘ SEKCJĘ ARTYKUŁU ===")
    current_section = next((s for s in state["outline"] if not s["is_approved"]), None)
    if not current_section: return {}
    
    current_section["revision_count"] += 1
    print(f"📝 Sekcja: '{current_section['title']}' (Próba #{current_section['revision_count']})")
    
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
Każdy śródtytuł musi mieć co najmniej dwa akapity. Jeśli to zasadne, stosuj wypunktowania i pogrubienia - ale nie w nadmiarze. Upewnij się, że tekst jest unikalny i wartościowy, bez powtórzeń.
"""
    if current_section.get("critique"):
        instruction += f"""\n
**POPRAWKI OD KRYTYKA:** Twoja poprzednia wersja tej sekcji została odrzucona. Uwagi: {current_section["critique"]}. Napisz tę sekcję od nowa, uwzględniając te uwagi.
"""
        print(f"🔄 Poprawiam sekcję na podstawie uwag: {current_section['critique'][:100]}...")

    print("🤖 Generuję treść sekcji...")
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=instruction)]
    response = llm.invoke(messages)
    current_section["draft"] = response.content
    
    print("📄 FRAGMENT WYGENEROWANEJ SEKCJI:")
    preview = response.content[:400].replace('\n', ' ')
    print(f"   {preview}...")
    print("✅ Sekcja napisana!")
    return {"outline": state["outline"]}

def section_critic_node(state: ArticleWorkflowState) -> dict:
    print("📝 === OCENIAM JAKOŚĆ SEKCJI ===")
    current_section_index = -1
    for i, s in enumerate(state["outline"]):
        if s.get("revision_count") > 0 and not s.get("is_approved"):
            current_section_index = i
            break
            
    if current_section_index == -1: return {}

    current_section = state["outline"][current_section_index]
    print(f"🔍 Oceniam sekcję: '{current_section['title']}'")
    
    llm = state["llm"]

    outline_context = []
    for i, section in enumerate(state["outline"]):
        if i < current_section_index:
            status = "✅ Ukończono"
        elif i == current_section_index:
            status = "🔍 OCENIAM TERAZ"
        else:
            status = "⏳ Kolejka"
        outline_context.append(f"{i+1}. {section['title']} ({status})")
    
    outline_context_str = "\n".join(outline_context)

    prompt = f"""Jesteś doświadczonym redaktorem. Twoim zadaniem jest ocena jakości i zgodności z personą fragmentu tekstu w kontekście całego artykułu.

**Struktura całego artykułu:**
---
{outline_context_str}
---

**Twoje zadania:**
1. Oceń treść sekcji oznaczonej jako 'OCENIAM TERAZ' - czy jest wartościowa, unikalna i dobrze napisana.
2. Sprawdź zgodność z personą: {state["persona"]["name"]}
3. Oceń w kontekście całego artykułu.

Odpowiedz w formacie JSON: {{"decision": "APPROVE", "critique": "Twoje uwagi dotyczące TYLKO ocenianej sekcji."}}.

**Tekst do oceny (sekcja: "{current_section['title']}"):**
---
{current_section["draft"]}
---
"""
    print("🤖 Oceniam jakość treści...")
    response = llm.invoke([HumanMessage(content=prompt)])
    raw_response_content = response.content

    try:
        json_str = extract_json_from_string(raw_response_content) 
        if not json_str:
            raise json.JSONDecodeError("Nie znaleziono bloku JSON w odpowiedzi.", raw_response_content, 0)
        
        critique_json = json.loads(json_str)
        decision = critique_json.get("decision", "REVISE").upper()
        critique = critique_json.get("critique", "Brak uwag.")
        
        if decision == "APPROVE":
            current_section["is_approved"] = True
            current_section["critique"] = None
            print(f"👍 SEKCJA ZAAKCEPTOWANA!")
            print(f"💬 Komentarz: {critique}")
        else:
            current_section["is_approved"] = False
            current_section["critique"] = critique
            print(f"👎 SEKCJA ODRZUCONA!")
            print(f"💬 Uwagi: {critique}")
    except json.JSONDecodeError:
        current_section["is_approved"] = False
        current_section["critique"] = "Błąd formatu JSON w odpowiedzi krytyka."
        print(f"❌ Błąd formatu JSON w odpowiedzi krytyka.")
        print(f"📄 Surowa odpowiedź: {raw_response_content[:200]}...")
    
    return {"outline": state["outline"]}

def assembler_node(state: ArticleWorkflowState) -> dict:
    print("⚙️ === SKŁADAM ARTYKUŁ ===")
    approved_sections = [s for s in state["outline"] if s["is_approved"] and s["draft"]]
    print(f"📋 Składam {len(approved_sections)} zatwierdzonych sekcji:")
    
    for i, section in enumerate(approved_sections, 1):
        word_count = len(section["draft"].split())
        print(f"   {i}. {section['title']} ({word_count} słów)")
    
    article_body = "\n\n".join(f"## {s['title']}\n\n{s['draft']}" for s in approved_sections)
    total_words = len(article_body.split())
    print(f"📊 Łączna długość treści: {total_words} słów")
    print("✅ Główna treść artykułu została złożona!")
    return {"assembled_body": article_body}

def introduction_writer_node(state: ArticleWorkflowState) -> dict:
    print("🚀 === TWORZĘ WSTĘP I KOMPLETNY ARTYKUŁ ===")
    llm = state["llm"]
    
    # Najpierw generujemy nagłówek H1
    print("🤖 Generuję nagłówek H1...")
    h1_title_prompt = f"""Na podstawie słowa kluczowego "{state["keyword"]}" i persony "{state["persona"]["name"]}", wygeneruj chwytliwy i zoptymalizowany pod SEO nagłówek H1 dla artykułu. Zwróć tylko nagłówek, bez dodatkowych komentarzy."""
    h1_title = llm.invoke([HumanMessage(content=h1_title_prompt)]).content.strip()
    print(f"📰 Nagłówek H1: {h1_title}")
    
    # Następnie generujemy wstęp
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
    print("🤖 Generuję angażujący wstęp...")
    response = llm.invoke([HumanMessage(content=prompt)])
    
    word_count = len(response.content.split())
    print("📄 FRAGMENT WSTĘPU:")
    preview = response.content[:300].replace('\n', ' ')
    print(f"   {preview}...")
    print(f"📊 Długość wstępu: {word_count} słów")
    
    # Składamy kompletny artykuł RAW (przed final editorem)
    raw_article = f"# {h1_title}\n\n{response.content}\n\n{state['assembled_body']}"
    total_words_raw = len(raw_article.split())
    
    print(f"📊 KOMPLETNY ARTYKUŁ RAW (przed szlifowaniem):")
    print(f"   📝 Słowa: {total_words_raw}")
    print(f"   🔤 Znaki: {len(raw_article)}")
    print("✅ Wstęp i artykuł RAW wygenerowane!")
    
    return {
        "introduction": response.content,
        "h1_title": h1_title,
        "raw_article": raw_article  # NOWE POLE - artykuł przed szlifowaniem
    }

def final_editor_node(state: ArticleWorkflowState) -> dict:
    print("✨ === FINALNE SZLIFOWANIE ===")
    llm = state["llm"]
    
    # Używamy gotowego artykułu RAW z poprzedniego kroku
    raw_article = state.get("raw_article")
    if not raw_article:
        print("⚠️ Brak artykułu RAW - tworzę go na nowo")
        h1_title = state.get("h1_title", f"Artykuł o: {state['keyword']}")
        raw_article = f"# {h1_title}\n\n{state['introduction']}\n\n{state['assembled_body']}"

    prompt = f"""Jesteś redaktorem końcowym. Twoim zadaniem jest ostatni szlif poniższego, kompletnego artykułu. Popraw błędy gramatyczne i stylistyczne, powtórzenia wyrazów. Upewnij się, że przejścia między wstępem a resztą tekstu są płynne i że całość jest spójna. Sprawdź, czy artykuł jest UX-friendly (zawiera wypunktowania i pogrubienia - ale nie w nadmiarze). Nie zmieniaj sensu ani tonu. Zwróć tylko i wyłącznie finalną, 'wypolerowaną' wersję artykułu.

Artykuł do redakcji:
---
{raw_article}
---"""
    
    print("🤖 Wykonuję finalne szlifowanie...")
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # Statystyki porównawcze
    raw_words = len(raw_article.split())
    final_words = len(response.content.split())
    raw_chars = len(raw_article)
    final_chars = len(response.content)
    
    print(f"📊 PORÓWNANIE WERSJI:")
    print(f"   📄 RAW:   {raw_words} słów, {raw_chars} znaków")
    print(f"   ✨ FINAL: {final_words} słów, {final_chars} znaków")
    print(f"   📈 Zmiana: {final_words - raw_words:+d} słów, {final_chars - raw_chars:+d} znaków")
    print("✅ Artykuł finalnie zredagowany i gotowy do publikacji!")
    
    return {"final_article": response.content}

def should_continue_outlining(state: ArticleWorkflowState) -> str:
    print("🤔 === DECYZJA O KONSPEKCIE ===")
    if state.get("outline_critique"):
        if state.get("outline_revision_count", 0) >= 3:
            print("⚠️ Osiągnięto limit poprawek konspektu (3). Akceptuję siłą.")
            return "start_writing"
        print("🔄 Konspekt wymaga poprawek. Wracam do generatora.")
        return "revise_outline"
    print("✅ Konspekt zatwierdzony. Przechodzę do pisania sekcji.")
    return "start_writing"

def should_continue_writing(state: ArticleWorkflowState) -> str:
    print("🤔 === DECYZJA O SEKCJACH ===")
    if all(s.get("is_approved", False) for s in state["outline"]):
        print("✅ Wszystkie sekcje zatwierdzone. Przechodzę do składania artykułu.")
        return "assemble_article"
    
    work_in_progress_section = next((s for s in state["outline"] if not s.get("is_approved")), None)
    if not work_in_progress_section:
        print("‼️ Błąd logiczny: Brak niezatwierdzonych sekcji. Wymuszam składanie.")
        return "assemble_article"
    
    if work_in_progress_section.get("revision_count", 0) >= 3:
        print(f"⚠️ Osiągnięto limit poprawek dla sekcji '{work_in_progress_section['title']}' (3). Akceptuję siłą.")
        work_in_progress_section["is_approved"] = True
        if all(s.get("is_approved", False) for s in state["outline"]):
            print("✅ Wszystkie sekcje zatwierdzone po wymuszonej akceptacji.")
            return "assemble_article"
    
    print(f"🔄 Kontynuuję pętlę pisania/krytyki dla sekcji: '{work_in_progress_section['title']}'")
    return "write_section"
