# ✦ Lumina — Website

Ask anything → searches the live web → answers with citations. Each visitor uses their **own** API key (browser-only, never stored on the server).

Two versions inside:

| Folder | What | Run |
|---|---|---|
| `streamlit_app.py` (root) | Quick Streamlit version | `python -m streamlit run streamlit_app.py` → http://localhost:8501 |
| `backend/` + `frontend/` | Real React website + Python API | see below → http://localhost:5173 |

## Run the React website locally (2 terminals)

Terminal 1 — backend API:
```powershell
Set-Location "C:\Users\kapta\OneDrive\Desktop\perplexiy web\backend"
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

Terminal 2 — React site:
```powershell
Set-Location "C:\Users\kapta\OneDrive\Desktop\perplexiy web\frontend"
npm install
npm run dev
```

Open **http://localhost:5173** → ⚙️ Settings → paste YOUR key → ask anything.

- **OpenRouter**: `sk-or-v1...` + model `google/gemini-2.5-flash` (default)
- **Gemini direct**: key from https://aistudio.google.com/apikey

## How it works

```
React (port 5173)  --POST /api/ask {question, provider, api_key, depth}-->  FastAPI (port 8000)
        ↑                                                                              |
        └──────── {answer, sources[12], queries[1/3/5]} ───────────────────────────────┘
                              plan → parallel search → dedup → synthesize
```

## Publish for free

- Frontend → **Vercel/Netlify**: point at `frontend/`, set env `VITE_API_URL` to your backend URL.
- Backend → **Render/Railway**: point at `backend/`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- Streamlit alternative → **share.streamlit.io** with root `streamlit_app.py` (no secrets needed).

## Safety

- Keys travel per-request and live only in the visitor's browser (`localStorage`), never on disk or in git.
- `.gitignore` blocks `secrets.toml`, `.env`, `node_modules/`, `dist/` from being committed.
