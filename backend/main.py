"""Lumina — FastAPI backend.

POST /api/ask  {question, provider, api_key, model, depth} -> {answer, sources, queries}
GET  /api/health -> {ok: True}

Each caller sends their OWN key per request (never stored server-side).
Run:  uvicorn main:app --port 8000   (from this backend/ folder)
"""
import concurrent.futures
import os
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google import genai

try:
    from ddgs import DDGS
except ImportError:  # fallback for old envs
    from duckduckgo_search import DDGS

APP_URL = os.getenv("APP_URL", "http://localhost:5173")
GEMINI_MODEL = "gemini-3.6-flash"
OR_DEFAULT_MODEL = "openai/gpt-4o-mini"

app = FastAPI(title="Lumina API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # keys are per-user; safe to accept browser calls
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    provider: str = "openrouter"  # "openrouter" | "gemini"
    api_key: str = Field(min_length=8, max_length=500)
    model: str = ""  # optional override; defaults per provider
    depth: int = 3  # 1 | 3 | 5
    image_url: str = ""  # optional: http(s) URL or data:image/...;base64,... for vision


class Source(BaseModel):
    n: int
    title: str
    url: str
    domain: str
    snip: str


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    queries: list[str]


# ---------- LLM ----------
def llm_vision(question: str, image_url: str, api_key: str, model: str) -> str:
    """OpenRouter vision call — Python version of JS SDK chat.send with image_url."""
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": APP_URL,
            "X-Title": "Lumina",
        },
        json={
            "model": model or OR_DEFAULT_MODEL,
            "max_tokens": 2048,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": question or "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }],
        },
        timeout=90,
    )
    if r.status_code == 402:
        raise HTTPException(402, "OpenRouter credits exhausted. Top up at openrouter.ai/settings/credits or use Gemini direct.")
    if r.status_code == 401:
        raise HTTPException(401, "Invalid OpenRouter API key.")
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def llm_generate(prompt: str, provider: str, api_key: str, model: str) -> str:
    if provider == "openrouter":
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": APP_URL,
                "X-Title": "Lumina",
            },
            json={
                "model": model or OR_DEFAULT_MODEL,
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        if r.status_code == 402:
            raise HTTPException(402, "OpenRouter credits exhausted. Top up at openrouter.ai/settings/credits or use Gemini direct.")
        if r.status_code == 401:
            raise HTTPException(401, "Invalid OpenRouter API key.")
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    # gemini direct
    try:
        client = genai.Client(api_key=api_key)
        return client.models.generate_content(model=model or GEMINI_MODEL, contents=prompt).text
    except Exception as e:
        if "404" in str(e) or "NOT_FOUND" in str(e):
            raise HTTPException(400, f"Model not available: {model or GEMINI_MODEL}. Try gemini-3.6-flash.")
        raise HTTPException(502, f"Gemini error: {e}")


# ---------- Search ----------
def web_search(query: str, max_results: int = 4):
    with DDGS() as ddgs:
        return list(ddgs.text(query, region="us-en", safesearch="moderate", max_results=max_results))


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url


def plan_queries(question: str, n: int, llm) -> list[str]:
    if n <= 1:
        q = llm(f"Rewrite this question as a concise web search query. Return ONLY the query.\nQuestion: {question}\nSearch query:").strip().strip('"')
        return [q]
    raw = llm(
        f"Break this question into {n} diverse, concise web search queries covering different angles "
        f"(facts, recent news, expert analysis). Return ONLY the queries, one per line, no numbering.\nQuestion: {question}"
    ).strip()
    queries = [ln.strip().lstrip("0123456789.-) ").strip('"') for ln in raw.splitlines() if ln.strip()]
    if not queries:
        queries = [question]
    return queries[:n] if len(queries) >= n else (queries + [queries[-1]] * (n - len(queries)))


def deep_search(queries: list[str], per_query: int):
    hits: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(queries))) as ex:
        futs = [ex.submit(web_search, q, per_query) for q in queries]
        for f in concurrent.futures.as_completed(futs):
            try:
                hits.extend(f.result() or [])
            except Exception:
                continue
    seen, uniq = set(), []
    for r in hits:
        href = (r.get("href") or "").split("#")[0]
        if not href or href in seen:
            continue
        seen.add(href)
        uniq.append(r)
    out = []
    for i, r in enumerate(uniq[:12], 1):
        out.append({
            "n": i,
            "title": r.get("title", "No title"),
            "url": r.get("href", ""),
            "domain": domain_of(r.get("href", "")),
            "snip": (r.get("body", "") or "")[:260],
        })
    return out


# ---------- Routes ----------
@app.get("/")
def root():
    return {
        "service": "Lumina API",
        "status": "live",
        "usage": "POST /api/ask with {question, provider, api_key, depth}",
        "health": "/api/health",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    provider = req.provider.lower().strip()
    if provider not in ("openrouter", "gemini"):
        raise HTTPException(400, "provider must be 'openrouter' or 'gemini'")
    depth = req.depth if req.depth in (1, 3, 5) else 3
    image_url = (req.image_url or "").strip()

    # ---- Vision path: image attached -> direct OpenRouter vision, no web search ----
    if image_url:
        if provider != "openrouter":
            raise HTTPException(400, "Image questions need provider='openrouter' (e.g. model openai/gpt-4o-mini).")
        try:
            answer = llm_vision(req.question, image_url, req.api_key, req.model.strip())
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Vision failed: {e}")
        return AskResponse(answer=answer, sources=[], queries=[req.question])

    def llm(prompt: str) -> str:
        return llm_generate(prompt, provider, req.api_key, req.model.strip())

    try:
        queries = plan_queries(req.question, depth, llm)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Planning failed: {e}")

    per = 5 if depth <= 1 else (4 if depth <= 3 else 3)
    sources = deep_search(queries, per)
    if not sources:
        return AskResponse(answer="No web results found. Try rephrasing your question.", sources=[], queries=queries)

    context = "".join(f"\n[{s['n']}] {s['title']}\n{s['snip']}\nURL: {s['url']}\n" for s in sources)
    prompt = f"""You are Lumina, a deep-research assistant.
Answer using ONLY the {len(sources)} sources below, researched from {len(queries)} angles: {", ".join(queries)}.
Rules:
- Start with a 2-3 sentence direct answer.
- Then detailed breakdown with short paragraphs + bullets.
- Compare viewpoints when sources disagree; note recency when relevant.
- Put [1], [2] style citations inline after EVERY factual claim.
- End with a one-line verdict/takeaway.

Question: {req.question}

Sources:
{context}

Answer (with citations):"""
    try:
        answer = llm(prompt)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Answer generation failed: {e}")
    return AskResponse(answer=answer, sources=[Source(**s) for s in sources], queries=queries)
