import os
import re
import json
import time
import html
import random
import requests
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from langchain_core.messages import HumanMessage, SystemMessage
from state import ArticleWorkflowState
from config import Config

# ---------- Utils ----------

def _clean_text(s: str) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _extract_main_content(html_content: bytes) -> str:
    soup = BeautifulSoup(html_content, "html.parser")

    # wywal śmieci
    for tag in soup(["script", "style", "noscript", "header", "footer", "aside", "nav"]):
        tag.decompose()

    # heurystyki main-content
    candidates = []
    selectors = [
        "article", "main", "#content", "[role=main]",
        "div[itemprop=articleBody]", ".post-content", ".entry-content", ".article-content"
    ]
    for sel in selectors:
        for el in soup.select(sel):
            txt = _clean_text(el.get_text(" ", strip=True))
            if len(txt) > 400:
                candidates.append(txt)

    if candidates:
        candidates.sort(key=len, reverse=True)
        return candidates[0]

    # fallback: cały tekst
    return _clean_text(soup.get_text(" ", strip=True))

def scrape_website(url: str, timeout: int = 15) -> str:
    try:
        headers = {
            "User-Agent": f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          f"(KHTML, like Gecko) Chrome/123.0.{random.randint(1000,9999)}.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        text = _extract_main_content(r.content)
        # przytnij do sensownego rozmiaru
        return text[:8000]
    except Exception as e:
        print(f"Scrape error for {url}: {e}")
        return ""

def parse_json_strict(txt: str) -> Any:
    """
    Bardziej odporny parser JSON: obcina backticki, szuka pierwszego poprawnego JSON.
    """
    candidates = []
    s = txt.strip()
    s = s.strip("`").strip()
    candidates.append(s)
    # spróbuj wyłuskać listę/obiekt
    m = re.search(r"(\[.*\]|\{.*\})", s, re.DOTALL)
    if m:
        candidates.append(m.group(1))

    for c in candidates:
        try:
            return json.loads(c)
        except Exception:
            continue
    raise ValueError("JSON parse failed")

# ---------- Nodes ----------

def researcher_node(state: ArticleWorkflowState) -> dict:
    print("🕵️ Research start")
    keyword = state["keyword"]
    google_api_key = os.getenv("GOOGLE_API_KEY")
    google_cx = os.getenv("GOOGLE_CX")

    urls: List[str] = []
    if not google_api_key or not google_cx:
        print("⚠️ Brak Google CSE. Podaj ręcznie 3–5 URL w przyszłości. Lecę bez SERP.")
    else:
        google_search = build("customsearch", "v1", developerKey=google_api_key)
        for attempt in range(3):
            try:
                res = google_search.cse().list(
                    q=keyword, cx=google_cx, num=10, gl="pl", hl="pl", lr="lang_pl"
                ).execute()
                urls = [i["link"] for i in res.get("items", [])][:10]
                break
            except Exception as e:
                print(f"CSE attempt {attempt+1} error: {e}")
                time.sleep(1 + attempt)
        urls = urls[:8]  # i tak nie potrzebujemy więcej

    print(f"🔗 URLs: {len(urls)}")
    chunks: List[str] = []
    for i, u in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {u}")
        txt = scrape_website(u)
        if not txt:
            continue

        # priorytetyzacja fragmentów z keywordem
        para = [p.strip() for p in re.split(r"(?<=\.)\s+", txt) if p.strip()]
        hit = [p for p in para if keyword.lower() in p.lower()]
        keep = " ".join(hit) if hit else txt
        chunks.append(f"--- SOURCE: {u} ---\n{keep[:6000]}\n")

    corpus = "\n\n".join(chunks)
    # hard cap całości
    if len(corpus) > 50000:
        corpus = corpus[:50000]

    if not corpus:
        corpus = f"Brak treści z konkurencji. Napisz artykuł o: {keyword} bazując na wiedzy ogólnej i personie."

    # mini podsumowanie researchem przez GPT-5 (opcjonalnie, ale daje porządek)
    llm = state["llm"]
    summary_prompt = f"""Stwórz zwięzłe podsumowanie researchu dla hasła: {keyword}.
Wypunktuj:
- główne tematy i byty
- pytania użytkowników (PAA-style)
- luki i unikalne kąty, które warto dodać

Źródła:
{corpus[:24000]}"""
    summary = llm.invoke([HumanMessage(content=summary_prompt)]).content.strip()

    print("✅ Research done")
    return {
        "research_corpus": corpus,
        "research_summary": summary,
        "raw_research_data": {"urls": urls}
    }

def outline_generator_node(state: ArticleWorkflowState) -> dict:
    print("📋 Outline")
    llm = state["llm"]
    persona = state["persona"]
    keyword = state["keyword"]

    prompt = f"""Jesteś strategiem treści. Na podstawie researchu i persony zaproponuj konspekt artykułu w JSON.

Zasady:
- 4–7 sekcji H2
- opcjonalne H3 jako lista
- dopasowanie do persony
- zero komentarzy, czysty JSON

Persona: {persona['name']} — {persona['prompt'][:600]}

Research summary:
{state['research_summary']}

Odpowiedz JSON-em w formacie:
[
  {{"h2": "Tytuł H2", "h3": ["Podpunkt 1","Podpunkt 2"]}},
  ...
]
"""
    raw = llm.invoke([HumanMessage(content=prompt)]).content
    data = parse_json_strict(raw)

    if not isinstance(data, list) or not (4 <= len(data) <= 7):
        raise ValueError("Konspekt ma złą liczbę sekcji (wymagane 4–7).")

    # sanity check format
    outline = []
    for item in data:
        if not isinstance(item, dict) or "h2" not in item:
            raise ValueError("Nieprawidłowy format elementu konspektu.")
        h2 = _clean_text(item["h2"])
        h3 = item.get("h3", [])
        if h3 and not isinstance(h3, list):
            h3 = []
        outline.append({"h2": h2, "h3": [ _clean_text(x) for x in h3 ]})

    print("✅ Outline done")
    return {"outline": outline}

def full_article_writer_node(state: ArticleWorkflowState) -> dict:
    print("✍️ Full article")
    llm = state["llm"]
    persona = state["persona"]
    keyword = state["keyword"]
    outline = state["outline"]
    research_summary = state["research_summary"]
    corpus = state.get("research_corpus", "")
    if not corpus:
        corpus = f"(Brak korpusu researchu. Pisz na bazie podsumowania i persony. Temat: {keyword})"

    instruction = f"""Napisz kompletny artykuł SEO na temat: "{keyword}".
Zasady:
- używaj konspektu poniżej
- każdy H2 minimum 2–4 akapity
- stosuj wypunktowania i pogrubienia oszczędnie
- naturalnie uwzględnij wnioski z researchu
- styl persony ma być zachowany
- język polski
- wygeneruj treść z nagłówkami H2/H3 (bez meta na razie)
- akapity mają być pełnymi, spójnymi wypowiedziami, nie urywkami
- pisz w sposób naturalny, unikaj generycznych zwrotków mogących wskazywć na AI.

Persona:
{persona['name']} — {persona['prompt'][:800]}

Konspekt (JSON):
{json.dumps(outline, ensure_ascii=False)}

Research summary:
{research_summary}

Fragmenty z konkurencji (wybrane):
{corpus[:20000]}
"""
    sys_msg = SystemMessage(content="Jesteś doświadczonym autorem SEO. Pisz klarownie, rzeczowo i bez lania wody.")
    out = llm.invoke([sys_msg, HumanMessage(content=instruction)]).content

    h1_prompt = f'Wygeneruj krótki, chwytliwy H1 dla artykułu o: "{keyword}". Zwróć sam H1, bez cudzysłowów.'
    h1 = llm.invoke([HumanMessage(content=h1_prompt)]).content.strip().strip('"').strip("'")

    article_md = f"# {h1}\n\n{out}".strip()
    print("✅ Article done")
    return {"raw_article": article_md, "h1_title": h1}

def final_editor_node(state: ArticleWorkflowState) -> dict:
    print("✨ Polish")
    llm = state["llm"]
    raw_article = state["raw_article"][:30000]  # safety cap

    prompt = f"""Wykonaj końcowe szlifowanie tekstu: usuń powtórzenia, popraw styl i spójność.
Nie zmieniaj sensu, nie skracaj agresywnie. Zachowaj nagłówki. Sprawdź poprawność w języku polskim. 
Sprawdź, czy treść jest atrakcyjna dla czytelnika pod względem czytelności i UX.

Zwróć tylko poprawiony artykuł (Markdown).
---
{raw_article}
---"""
    final_article = llm.invoke([HumanMessage(content=prompt)]).content.strip()
    print("✅ Polish done")
    return {"final_article": final_article}

def seo_generator_node(state: ArticleWorkflowState) -> dict:
    print("🔧 SEO extras")
    llm = state["llm"]
    article = state["final_article"]
    keyword = state["keyword"]

    meta_prompt = f"""Na podstawie artykułu wygeneruj:
- Meta Title: 50–60 znaków, zawiera frazę docelową {keyword} lub jej naturalny wariant.
- Meta Description: 140–160 znaków, konkretna obietnica wartości.

Zwróć JSON:
{{"title": "...", "description": "..."}}.

Artykuł:
{article[:12000]}
"""
    raw = llm.invoke([HumanMessage(content=meta_prompt)]).content
    meta = parse_json_strict(raw)
    title = _clean_text(meta.get("title", ""))[:70]
    desc = _clean_text(meta.get("description", ""))[:200]

    print("✅ SEO done")
    return {"meta_title": title, "meta_description": desc}
