"""Lumina — website (Streamlit Cloud) version.

Each visitor pastes their OWN API key in the sidebar (session-only, never stored).
No secrets file needed on the server. Deploy: push this folder to GitHub -> share.streamlit.io.
"""
import os
import time
import base64
import concurrent.futures
import requests
from urllib.parse import urlparse
import streamlit as st
from google import genai
try:
    from ddgs import DDGS  # new package (duckduckgo-search renamed, old returns empty)
except ImportError:
    from duckduckgo_search import DDGS

# ---------- CONFIG ----------
MODEL = "gemini-3.6-flash"  # Gemini-direct backend
OR_DEFAULT_MODEL = "openai/gpt-4o-mini"  # OpenRouter backend (vision-capable, cheap)
OR_PRESETS = [
    "openai/gpt-4o-mini",
    "google/gemini-2.5-flash",
    "anthropic/claude-3.5-sonnet",
    "meta-llama/llama-3.1-8b-instruct",
]
APP_URL = os.getenv("APP_URL", "https://share.streamlit.io")  # OpenRouter referer header
PAGE_TITLE = "Lumina"
TEAL = "#20b8cd"

st.set_page_config(page_title=PAGE_TITLE, page_icon="🔍", layout="centered")

# ---------- STYLES (Lumina theme) ----------
st.markdown(f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] {{ font-family: 'Inter', system-ui, sans-serif; }}
  .block-container {{ max-width: 820px; padding-top: 2rem; padding-bottom: 6rem; }}
  header[data-testid="stHeader"] {{ background: transparent; }}
  /* hero */
  .hero {{ text-align: center; padding: 3.2rem 1rem 1.2rem; }}
  .hero-logo {{
    width: 52px; height: 52px; margin: 0 auto 14px; border-radius: 14px;
    background: linear-gradient(135deg, {TEAL}, #0e7c8a);
    display: flex; align-items: center; justify-content: center;
    font-size: 26px; color: white; box-shadow: 0 8px 24px rgba(32,184,205,.35);
  }}
  .hero h1 {{ font-size: 2.4rem; font-weight: 600; letter-spacing: -0.02em; margin: 0; color: #111827; }}
  .hero p {{ color: #6b7280; margin-top: .5rem; font-size: 1.02rem; }}
  /* top bar */
  .topbar {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: .5rem; }}
  .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.05rem; }}
  .brand-mark {{
    width: 32px; height: 32px; border-radius: 9px; background: linear-gradient(135deg, {TEAL}, #0e7c8a);
    display: inline-flex; align-items: center; justify-content: center; color: #fff; font-size: 18px;
  }}
  .model-badge {{
    font-size: .78rem; color: #0e7c8a; background: rgba(32,184,205,.12);
    border: 1px solid rgba(32,184,205,.35); padding: 4px 10px; border-radius: 999px; font-weight: 600;
  }}
  /* suggestion pills */
  .sugg-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 1.2rem auto 0; max-width: 640px; }}
  @media (max-width: 640px) {{ .sugg-grid {{ grid-template-columns: 1fr; }} }}
  div[data-testid="stButton"] > button {{
    border-radius: 12px; border: 1px solid #e5e7eb; background: #fff;
    padding: .7rem .9rem; text-align: left; font-size: .92rem; line-height: 1.35;
    color: #111827; box-shadow: 0 1px 2px rgba(0,0,0,.04); transition: all .15s ease;
  }}
  div[data-testid="stButton"] > button:hover {{
    border-color: {TEAL}; box-shadow: 0 4px 14px rgba(32,184,205,.18); color: #0b5560;
  }}
  /* Q + answer cards */
  .q-title {{ font-size: 1.45rem; font-weight: 700; letter-spacing: -0.01em; margin: 1.6rem 0 .8rem; color: #111827; }}
  .answer-card {{
    background: #fff; border: 1px solid #ececee; border-radius: 16px;
    padding: 1.15rem 1.25rem; box-shadow: 0 2px 12px rgba(0,0,0,.04); line-height: 1.65; color: #111827;
  }}
  .answer-card p, .answer-card li {{ color: #111827; }}
  .answer-card a {{ color: #0e7c8a; }}
  /* bordered containers (native markdown answers) look like cards */
  div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 16px; box-shadow: 0 2px 12px rgba(0,0,0,.04); background: #fff; border: 1px solid #ececee;
  }}
  div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stMarkdownContainer"] p,
  div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stMarkdownContainer"] li {{
    color: #111827;
  }}
  .src-card {{
    background: #fff; border: 1px solid #e8e8ea; border-radius: 12px; padding: .65rem .7rem;
    height: 100%; transition: all .15s ease; color: #111827;
  }}
  .src-card:hover {{ border-color: {TEAL}; box-shadow: 0 4px 14px rgba(32,184,205,.16); }}
  .src-card a {{ text-decoration: none; color: #111827; font-size: .85rem; font-weight: 600; line-height: 1.35; }}
  .src-domain {{ font-size: .75rem; color: #6b7280; margin-top: 4px; display: flex; align-items: center; gap: 6px; }}
  .src-num {{
    font-size: .7rem; font-weight: 700; color: #0e7c8a; background: rgba(32,184,205,.14);
    border-radius: 6px; padding: 1px 6px; margin-right: 4px;
  }}
  .step-pill {{
    display: inline-block; font-size: .75rem; font-weight: 600; color: #374151;
    background: #f3f4f6; border: 1px solid #e5e7eb; padding: 3px 10px; border-radius: 999px; margin: 2px 4px 2px 0;
  }}
  /* chat input */
  div[data-testid="stChatInput"] {{ max-width: 820px; margin: 0 auto; }}
  div[data-testid="stChatInput"] textarea {{ border-radius: 16px !important; border: 1.5px solid #e2e2e5 !important; }}
  div[data-testid="stChatInput"] textarea:focus {{ border-color: {TEAL} !important; box-shadow: 0 0 0 4px rgba(32,184,205,.15) !important; }}
  .footer {{ text-align: center; color: #9ca3af; font-size: .78rem; margin-top: 2rem; }}
  /* hide default chat avatars spacing */
  div[data-testid="stChatMessage"] {{ background: transparent; border: none; padding: .4rem 0; }}
</style>
""", unsafe_allow_html=True)

# ---------- API KEYS (per-visitor, session-only — nothing baked in) ----------
def _load_secret(name):
    v = os.getenv(name, "")
    try:
        s = st.secrets.get(name, "")
        if s:
            return s
    except Exception:
        pass
    return v

if "gemini_key" not in st.session_state:
    st.session_state.gemini_key = _load_secret("GEMINI_API_KEY")
if "or_key" not in st.session_state:
    st.session_state.or_key = _load_secret("OPENROUTER_API_KEY")
if "provider" not in st.session_state:
    st.session_state.provider = "OpenRouter"
if "or_model" not in st.session_state:
    st.session_state.or_model = OR_DEFAULT_MODEL

with st.sidebar:
    st.header("⚙️ Settings")
    st.info("🔑 Paste **YOUR** key — it stays in your session only and is never stored or shared.", icon="🔒")
    st.subheader("🤖 AI Provider")
    provider = st.radio(
        "Choose backend",
        ["OpenRouter", "Gemini direct"],
        index=0 if st.session_state.provider == "OpenRouter" else 1,
        help="OpenRouter = uses your sk-or-v1 key. Gemini direct = uses a Gemini API key.",
    )
    st.session_state.provider = provider
    if provider == "OpenRouter":
        or_in = st.text_input(
            "OpenRouter API Key", value=st.session_state.or_key, type="password",
            placeholder="sk-or-v1...",
        )
        st.session_state.or_key = or_in.strip()
        # Model presets + custom (your snippet uses openai/gpt-4o-mini)
        preset = st.selectbox(
            "OpenRouter model",
            OR_PRESETS + ["✏️ Custom…"],
            index=0 if st.session_state.or_model in OR_PRESETS else len(OR_PRESETS),
        )
        if preset == "✏️ Custom…":
            or_model_in = st.text_input("Custom model id", value=st.session_state.or_model if st.session_state.or_model not in OR_PRESETS else "")
            st.session_state.or_model = (or_model_in.strip() or OR_DEFAULT_MODEL)
        else:
            st.session_state.or_model = preset
        st.caption("openrouter.ai · many models, pay-as-you-go")
        st.link_button("Get OpenRouter Key", "https://openrouter.ai/keys")
    else:
        g_in = st.text_input(
            "Gemini API Key", value=st.session_state.gemini_key, type="password",
            placeholder="Paste key from aistudio.google.com",
        )
        st.session_state.gemini_key = g_in.strip()
        st.caption("Free tier: 15 req/min · 1M tokens/day")
        st.link_button("Get FREE Gemini Key", "https://aistudio.google.com/apikey")
    st.divider()
    st.subheader("🔬 Research depth")
    depth = st.radio(
        "How many angles to research?",
        ["⚡ Quick (1 query)", "🔍 Standard (3 queries)", "🧠 Deep (5 queries)"],
        index=1,
        help="Quick = 1 search. Standard = 3 parallel searches from different angles. Deep = 5 parallel searches.",
    )
    DEPTH_MAP = {"⚡ Quick (1 query)": 1, "🔍 Standard (3 queries)": 3, "🧠 Deep (5 queries)": 5}
    N_QUERIES = DEPTH_MAP[depth]
    st.divider()
    ACTIVE_MODEL = st.session_state.or_model if st.session_state.provider == "OpenRouter" else MODEL
    st.caption(f"Model: `{ACTIVE_MODEL}` · Search: DuckDuckGo (free)")

PROVIDER = st.session_state.provider
GEMINI_API_KEY = st.session_state.gemini_key
OPENROUTER_API_KEY = st.session_state.or_key
OPENROUTER_MODEL = st.session_state.or_model

if PROVIDER == "OpenRouter" and not OPENROUTER_API_KEY:
    st.markdown('<div class="hero"><div class="hero-logo">🔍</div><h1>What do you want to know?</h1><p>Paste your OpenRouter key (sk-or-v1…) in the sidebar to start. Your key never leaves your session.</p></div>', unsafe_allow_html=True)
    st.stop()
if PROVIDER == "Gemini direct" and (not GEMINI_API_KEY or GEMINI_API_KEY == "PASTE_YOUR_KEY_HERE"):
    st.markdown('<div class="hero"><div class="hero-logo">🔍</div><h1>What do you want to know?</h1><p>Paste your Gemini API key in the sidebar to start. Your key never leaves your session.</p></div>', unsafe_allow_html=True)
    st.stop()

_gemini_client = None
def _gemini():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client

def llm_generate(prompt):
    """Route to active provider. Returns plain text."""
    if st.session_state.provider == "OpenRouter":
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": APP_URL,
                "X-Title": "Lumina",
            },
            json={
                "model": OPENROUTER_MODEL,
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    return _gemini().models.generate_content(model=MODEL, contents=prompt).text


def llm_vision(question, image_url):
    """Vision Q&A via OpenRouter (e.g. openai/gpt-4o-mini). Same as JS SDK chat.send with image_url."""
    if st.session_state.provider != "OpenRouter":
        raise RuntimeError("Image questions need Provider = OpenRouter (switch in sidebar).")
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": APP_URL,
            "X-Title": "Lumina",
        },
        json={
            "model": OPENROUTER_MODEL,
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
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _upload_to_data_url(uploaded):
    mime = getattr(uploaded, "type", "") or "image/jpeg"
    b64 = base64.b64encode(uploaded.getvalue()).decode()
    return f"data:{mime};base64,{b64}"

# ---------- STATE ----------
if "messages" not in st.session_state:
    st.session_state.messages = []  # {role, content, sources:[(i,title,url,snip)], query}
if "pending" not in st.session_state:
    st.session_state.pending = None

# ---------- AGENT CORE (deep research: multiple angles, parallel) ----------
def web_search(query, max_results=5):
    """Free web search via DuckDuckGo (no API key needed)."""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, region="us-en", safesearch="moderate", max_results=max_results))
    return results

def plan_queries(user_query, n=3):
    """Ask the LLM to break the question into n diverse search queries (one per line)."""
    if n <= 1:
        p = llm_generate(
            f"Rewrite this question as a concise web search query. Return ONLY the query.\nQuestion: {user_query}\nSearch query:"
        ).strip().strip('"')
        return [p]
    prompt = (
        f"Break this question into {n} diverse, concise web search queries covering different angles "
        f"(facts, recent news, expert analysis). Return ONLY the queries, one per line, no numbering.\n"
        f"Question: {user_query}"
    )
    raw = llm_generate(prompt).strip()
    queries = [ln.strip().lstrip("0123456789.-) ").strip('"') for ln in raw.splitlines() if ln.strip()]
    # fallback: pad/truncate to n
    if not queries:
        queries = [user_query]
    return queries[:n] if len(queries) >= n else (queries + [queries[-1]] * (n - len(queries)))

def deep_search(queries, per_query=4):
    """Run all queries in parallel, dedup by URL. Returns sources [(i,title,url,snip)]."""
    all_hits = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(queries)) as ex:
        futs = {ex.submit(web_search, q, per_query): q for q in queries}
        for f in concurrent.futures.as_completed(futs):
            try:
                all_hits.extend(f.result() or [])
            except Exception:
                continue
    # dedup by href, keep first
    seen, uniq = set(), []
    for r in all_hits:
        href = (r.get("href") or "").split("#")[0]
        if not href or href in seen:
            continue
        seen.add(href)
        uniq.append(r)
    sources = []
    for i, r in enumerate(uniq[:12], 1):
        sources.append((i, r.get("title", "No title"), r.get("href", ""), (r.get("body", "") or "")[:260]))
    return sources

def synthesize(user_query, queries, sources):
    context = ""
    for i, title, href, snip in sources:
        context += f"\n[{i}] {title}\n{snip}\nURL: {href}\n"
    prompt = f"""You are Lumina, a deep-research assistant.
Answer using ONLY the {len(sources)} sources below, researched from {len(queries)} angles: {", ".join(queries)}.
Rules:
- Start with a 2-3 sentence direct answer.
- Then detailed breakdown with short paragraphs + bullets.
- Compare viewpoints when sources disagree; note recency when relevant.
- Put [1], [2] style citations inline after EVERY factual claim.
- End with a one-line verdict/takeaway.

Question: {user_query}

Sources:
{context}

Answer (with citations):"""
    return llm_generate(prompt)

def run_agent(user_query, n_queries=3):
    """Compat wrapper. Returns (answer, sources, queries)."""
    queries = plan_queries(user_query, n_queries)
    per = 5 if n_queries <= 1 else (4 if n_queries <= 3 else 3)
    sources = deep_search(queries, per)
    if not sources:
        return "No web results found. Try rephrasing your question.", [], queries
    return synthesize(user_query, queries, sources), sources, queries

def domain_of(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url

def favicon(url):
    try:
        d = domain_of(url)
        return f"https://www.google.com/s2/favicons?domain={d}&sz=32"
    except Exception:
        return ""

def render_sources(sources):
    if not sources:
        return
    st.markdown("**Sources**")
    cols = st.columns(3)
    for idx, (i, title, url, _snip) in enumerate(sources):
        with cols[idx % 3]:
            short = (title[:72] + "…") if len(title) > 74 else title
            st.markdown(
                f'<div class="src-card"><span class="src-num">{i}</span>'
                f'<a href="{url}" target="_blank">{short}</a>'
                f'<div class="src-domain"><img src="{favicon(url)}" width="14" height="14"/> {domain_of(url)}</div></div>',
                unsafe_allow_html=True,
            )

# ---------- TOP BAR ----------
c1, c2 = st.columns([1, 1])
with c1:
    st.markdown('<div class="brand"><span class="brand-mark">✦</span> lumina</div>', unsafe_allow_html=True)
with c2:
    r1, r2 = st.columns([1, 1])
    with r1:
        st.markdown(f'<div style="text-align:right"><span class="model-badge">⚡ {ACTIVE_MODEL}</span></div>', unsafe_allow_html=True)
    with r2:
        if st.button("＋ New thread", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pending = None
            st.session_state.pending_image = None
            st.session_state.attached_image = None
            st.session_state.attached_url = ""
            st.rerun()

# ---------- HERO (empty state) ----------
SUGGESTIONS = [
    ("🤖 Latest in AI", "What are the latest breakthroughs in AI this week?"),
    ("⚛️ Explain simply", "Explain quantum computing in simple terms with examples"),
    ("📈 Markets today", "What is happening in global markets today?"),
    ("🧬 Health tip", "What does science say about improving sleep quality?"),
]

if not st.session_state.messages:
    st.markdown('<div class="hero"><div class="hero-logo">✦</div><h1>What do you want to know?</h1><p>Ask anything → I search the live web → answer with citations</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="sugg-grid">', unsafe_allow_html=True)
    scols = st.columns(2)
    for i, (label, q) in enumerate(SUGGESTIONS):
        with scols[i % 2]:
            if st.button(f"{label}\n{q}", key=f"sugg_{i}", use_container_width=True):
                st.session_state.pending = q
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ---------- THREAD ----------
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="q-title">{msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("image"):
            try:
                st.image(msg["image"], width=420)
            except Exception:
                pass
        queries = msg.get("queries") or ([msg["query"]] if msg.get("query") else [])
        if queries:
            pills = " ".join(f'<span class="step-pill">🔍 {qq}</span>' for qq in queries)
            st.markdown(pills, unsafe_allow_html=True)
    else:
        n_src = len(msg.get("sources", []))
        n_q = len(msg.get("queries", [])) or (1 if msg.get("query") else 0)
        if n_src:
            st.caption(f"Researched {n_src} sources across {max(n_q,1)} angle(s)")
        elif msg.get("image_model"):
            st.caption(f"🖼️ Vision answer via `{msg.get('image_model')}`")
        render_sources(msg.get("sources", []))
        with st.container(border=True):
            st.markdown(msg["content"])

# ---------- IMAGE INPUT (vision via OpenRouter, e.g. openai/gpt-4o-mini) ----------
if "attached_image" not in st.session_state:
    st.session_state.attached_image = None
if "attached_url" not in st.session_state:
    st.session_state.attached_url = ""

with st.expander("📷 Image (optional — ask about a picture with gpt-4o-mini)", expanded=False):
    up = st.file_uploader("Upload image", type=["png", "jpg", "jpeg", "webp"])
    if up is not None:
        try:
            st.session_state.attached_image = _upload_to_data_url(up)
        except Exception as e:
            st.error(f"Could not read upload: {e}")
    url_in = st.text_input(
        "…or paste image URL",
        value=st.session_state.attached_url,
        placeholder="https://live.staticflickr.com/3851/14825276609_098cac593d_b.jpg",
    )
    st.session_state.attached_url = (url_in or "").strip()
    c_img1, c_img2 = st.columns([1, 1])
    with c_img1:
        if st.button("🖼️ Try sample image"):
            st.session_state.attached_url = "https://live.staticflickr.com/3851/14825276609_098cac593d_b.jpg"
            st.session_state.attached_image = None
            st.rerun()
    with c_img2:
        if st.button("✖ Clear image"):
            st.session_state.attached_image = None
            st.session_state.attached_url = ""
            st.rerun()
    effective_preview = st.session_state.attached_image or st.session_state.attached_url
    if effective_preview:
        st.caption("Attached — your next question will use vision:")
        try:
            st.image(effective_preview, width=320)
        except Exception:
            st.caption(effective_preview[:120])

# ---------- INPUT ----------
chat_val = st.chat_input("Ask anything… (attach image above for vision)")
if chat_val:
    st.session_state.pending = chat_val
    # snapshot attached image at submit time
    st.session_state.pending_image = st.session_state.attached_image or st.session_state.attached_url or None
    # clear attachment so next question starts fresh
    st.session_state.attached_image = None
    st.session_state.attached_url = ""
    st.rerun()

if st.session_state.pending:
    q = st.session_state.pending
    img = st.session_state.get("pending_image")
    st.session_state.pending = None
    st.session_state.pending_image = None
    # show question immediately
    st.session_state.messages.append({"role": "user", "content": q, "query": "", "queries": [], "image": img})
    st.markdown(f'<div class="q-title">{q}</div>', unsafe_allow_html=True)
    if img:
        try:
            st.image(img, width=420)
        except Exception:
            pass

    # ---- Vision path (image attached): direct OpenRouter image_url call ----
    if img:
        with st.status("🖼️ Reading image with OpenRouter vision…", expanded=True) as status:
            try:
                st.write(f"🤖 Model: `{OPENROUTER_MODEL}`")
                answer = llm_vision(q, img)
                status.update(label="✅ Done — vision answer", state="complete", expanded=False)
                st.session_state.messages.append({"role": "assistant", "content": answer, "sources": [], "queries": [], "query": "", "image_model": OPENROUTER_MODEL})
                st.rerun()
            except Exception as e:
                status.update(label="⚠️ Vision failed", state="error", expanded=False)
                reply = f"⚠️ Vision error: `{e}`\n\n- Provider must be **OpenRouter**\n- Model must support vision (e.g. `openai/gpt-4o-mini`)\n- Check key has credits"
                st.session_state.messages.append({"role": "assistant", "content": reply, "sources": [], "queries": [], "query": ""})
                st.rerun()

    n_q = N_QUERIES if "N_QUERIES" in dir() else 3

    with st.status(f"🔬 Deep research: {n_q} angle(s), parallel search…", expanded=True) as status:
        try:
            st.write(f"✍️ Planning {n_q} search angle(s)…")
            queries = plan_queries(q, n_q)
            for qq in queries:
                st.write(f"🔎 Angle: `{qq}`")
            per = 5 if n_q <= 1 else (4 if n_q <= 3 else 3)
            st.write(f"🌐 Searching {len(queries)} queries in parallel…")
            sources = deep_search(queries, per)
            if not sources:
                raise RuntimeError("EMPTY_RESULTS")
            uniq_domains = len({domain_of(u) for _, _, u, _ in sources})
            st.write(f"📄 Reading {len(sources)} sources from {uniq_domains} websites…")
            for _i, _t, _u, _s in sources[:6]:
                st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;[{_i}] {_t[:70]}")
            st.write("✨ Synthesizing cited answer…")
            answer = synthesize(q, queries, sources)
            status.update(label=f"✅ Done — {len(sources)} sources, {uniq_domains} sites", state="complete", expanded=False)
            st.session_state.messages[-1]["queries"] = queries
            st.session_state.messages[-1]["query"] = queries[0] if queries else ""
            st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources, "queries": queries, "query": queries[0] if queries else ""})
            st.rerun()
        except Exception as e:
            status.update(label="⚠️ Search failed", state="error", expanded=False)
            msg = str(e)
            if "EMPTY_RESULTS" in msg:
                reply = "No web results found. Try rephrasing your question."
            else:
                reply = f"⚠️ Error: `{e}`\n\n- Check API key\n- Rate limit? Wait 1 min\n- DuckDuckGo timeout? Try again"
            st.session_state.messages.append({"role": "assistant", "content": reply, "sources": [], "queries": [], "query": ""})
            st.rerun()

st.markdown('<div class="footer">🔒 Your API key stays in your session only — never stored. Answers include citations — always verify important facts.</div>', unsafe_allow_html=True)
