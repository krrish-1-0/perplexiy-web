import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const OR_DEFAULT = 'openai/gpt-4o-mini'
export const DOLPHIN_MODEL = 'cognitivecomputations/dolphin-mistral-24b-venice-edition'
const OR_PRESETS = [
  OR_DEFAULT,
  'google/gemini-2.5-flash',
  'anthropic/claude-3.5-sonnet',
  'meta-llama/llama-3.1-8b-instruct',
  DOLPHIN_MODEL,
]

const SUGGESTIONS = [
  { icon: '🤖', label: 'Latest in AI', q: 'What are the latest breakthroughs in AI this week?' },
  { icon: '⚛️', label: 'Explain simply', q: 'Explain quantum computing in simple terms with examples' },
  { icon: '📈', label: 'Markets today', q: 'What is happening in global markets today?' },
  { icon: '🧬', label: 'Health tip', q: 'What does science say about improving sleep quality?' },
  { icon: '🚀', label: 'Space news', q: 'What are the most exciting recent discoveries in space?' },
  { icon: '💻', label: 'Learn coding', q: 'What is the best way to learn Python as a beginner in 2026?' },
  { icon: '🌍', label: 'Climate', q: 'What is the latest progress on climate change solutions?' },
  { icon: '⚽', label: 'Sports buzz', q: 'What are the biggest sports headlines right now?' },
]

const FOLLOW_UPS = [
  "Explain it like I'm 5",
  'What are the latest updates?',
  'What are the pros and cons?',
  'Give real-world examples',
  'What do experts disagree on?',
]

const pick4 = () => [...SUGGESTIONS].sort(() => Math.random() - 0.5).slice(0, 4)

const STEPS = ['Planning angles', 'Searching the web', 'Reading sources', 'Writing answer']

const favicon = (domain) => `https://www.google.com/s2/favicons?domain=${domain}&sz=32`

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('px_theme') || 'light')
  const [provider, setProvider] = useState(() => localStorage.getItem('px_provider') || 'openrouter')
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('px_key') || '')
  const [model, setModel] = useState(() => localStorage.getItem('px_model') || OR_DEFAULT)
  const [depth, setDepth] = useState(3)
  const [showSettings, setShowSettings] = useState(false)
  const [messages, setMessages] = useState([]) // {role, content, sources, queries, image}
  const [input, setInput] = useState('')
  const [imageUrl, setImageUrl] = useState('') // http URL or data:image/...;base64 preview for vision
  const [loading, setLoading] = useState(false)
  const [stepIdx, setStepIdx] = useState(0)
  const [error, setError] = useState('')
  const [heroSugg, setHeroSugg] = useState(pick4)
  const [typed, setTyped] = useState(null) // typewriter progress for newest answer
  const animFor = useRef(-1)
  const bottomRef = useRef(null)
  const timers = useRef([])

  useEffect(() => {
    localStorage.setItem('px_theme', theme)
    localStorage.setItem('px_provider', provider)
    localStorage.setItem('px_key', apiKey)
    localStorage.setItem('px_model', model)
  }, [theme, provider, apiKey, model])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, stepIdx])

  // typewriter reveal for the newest assistant answer
  useEffect(() => {
    const last = messages[messages.length - 1]
    if (last?.role === 'assistant' && last.content && !last.content.startsWith('⚠️') && animFor.current !== messages.length) {
      animFor.current = messages.length
      const full = last.content.length
      setTyped(0)
      const id = setInterval(() => {
        setTyped((t) => {
          if (t === null) return t
          const next = t + Math.max(8, Math.ceil(full / 70))
          if (next >= full) {
            clearInterval(id)
            return full
          }
          return next
        })
      }, 28)
      return () => clearInterval(id)
    }
    if (!last || last.role !== 'assistant') setTyped(null)
  }, [messages])

  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  async function ask(question) {
    const q = (question ?? input).trim()
    if (!q || loading) return
    if (!apiKey.trim()) {
      setError('Paste your API key first (⚙️ Settings, top right). It stays in your browser only.')
      setShowSettings(true)
      return
    }
    const img = imageUrl.trim() || null
    if (img && provider !== 'openrouter') {
      setError('Image questions need Provider = OpenRouter with a vision model like openai/gpt-4o-mini.')
      return
    }
    setError('')
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: q, queries: [], image: img }])
    setImageUrl('')
    setLoading(true)
    setStepIdx(0)
    try {
      // progressive research timeline while the request runs
      timers.current = [
        setTimeout(() => setStepIdx(1), 2500),
        setTimeout(() => setStepIdx(2), 9000),
        setTimeout(() => setStepIdx(3), 16000),
      ]
      const res = await fetch(`${API}/api/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          provider,
          api_key: apiKey.trim(),
          model: provider === 'openrouter' ? model.trim() : '',
          depth,
          image_url: img || '',
        }),
      })
      timers.current.forEach(clearTimeout)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`)
      setMessages((m) => {
        const copy = [...m]
        copy[copy.length - 1] = { ...copy[copy.length - 1], queries: data.queries }
        return [...copy, { role: 'assistant', content: data.answer, sources: data.sources, queries: data.queries }]
      })
    } catch (e) {
      timers.current.forEach(clearTimeout)
      setMessages((m) => [...m, { role: 'assistant', content: `⚠️ ${e.message}`, sources: [], queries: [] }])
    } finally {
      setLoading(false)
    }
  }

  const activeModel = provider === 'openrouter' ? (model || OR_DEFAULT) : 'gemini-3.6-flash'
  const lastUserQ = () => [...messages].reverse().find((m) => m.role === 'user')?.content || ''
  const isNewestAnswer = (i, m) =>
    i === messages.length - 1 && m.role === 'assistant' && typed !== null && typed < m.content.length

  return (
    <div className={`app theme-${theme}${loading ? ' is-loading' : ''}`}>
      <div className="bg-orbs" aria-hidden="true"><span className="orb orb-a" /><span className="orb orb-b" /></div>
      <div className="page">
        <header className="topbar">
          <div className="brand"><span className="brand-mark">✦</span> lumina</div>
          <div className="top-actions">
            <span className="model-badge">⚡ {activeModel}</span>
            <button className="icon-btn" title="Toggle theme" onClick={() => setTheme((t) => (t === 'light' ? 'dark' : 'light'))}>
              {theme === 'light' ? '🌙' : '☀️'}
            </button>
            <button className="ghost-btn" onClick={() => setShowSettings((s) => !s)}>⚙️ Settings</button>
            <button className="ghost-btn primary" onClick={() => setMessages([])}>＋ New</button>
          </div>
        </header>

        {showSettings && (
          <div className="settings pop-in">
            <div className="lock-note">🔒 Your key stays in <b>your browser only</b> (localStorage) — sent with each request, never stored on the server.</div>
            <div className="set-row">
              <div>
                <label>AI Provider</label>
                <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                  <option value="openrouter">OpenRouter</option>
                  <option value="gemini">Gemini direct</option>
                </select>
              </div>
              <div>
                <label>Research depth</label>
                <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
                  <option value={1}>⚡ Quick (1 query)</option>
                  <option value={3}>🔍 Standard (3 queries)</option>
                  <option value={5}>🧠 Deep (5 queries)</option>
                </select>
              </div>
            </div>
            <label>{provider === 'openrouter' ? 'OpenRouter API Key (sk-or-v1…)' : 'Gemini API Key (AIza…)'}</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={provider === 'openrouter' ? 'sk-or-v1...' : 'AIza...'}
            />
            {provider === 'openrouter' && (
              <>
                <label>OpenRouter model</label>
                <select
                  value={OR_PRESETS.includes(model) ? model : '__custom__'}
                  onChange={(e) => {
                    if (e.target.value !== '__custom__') setModel(e.target.value)
                    else setModel('')
                  }}
                >
                  {OR_PRESETS.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                  <option value="__custom__">✏️ Custom…</option>
                </select>
                {!OR_PRESETS.includes(model) && (
                  <input
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder={DOLPHIN_MODEL}
                    style={{ marginTop: 8 }}
                  />
                )}
                <div style={{ fontSize: 12, opacity: 0.75, marginTop: 4 }}>
                  Text chat: any preset incl. Dolphin Venice. Vision (image): use {OR_DEFAULT}.
                </div>
                <label>Image (optional — vision)</label>
                <input
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  placeholder="https://...jpg  or upload below"
                />
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (!f) return
                    const rd = new FileReader()
                    rd.onload = () => setImageUrl(String(rd.result || ''))
                    rd.readAsDataURL(f)
                  }}
                />
                {imageUrl.trim() && (
                  <div style={{ marginTop: 8 }}>
                    <img src={imageUrl} alt="preview" style={{ maxWidth: 220, borderRadius: 10 }} />
                    <div><button className="ghost-btn" type="button" onClick={() => setImageUrl('')}>✖ Clear image</button></div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {messages.length === 0 && (
          <div className="hero fade-up">
            <div className="hero-badge">🔬 Deep research · 100% free stack</div>
            <div className="hero-logo">✦</div>
            <h1>What do you want to <span className="grad">know?</span></h1>
            <p>Ask anything → I search the live web from multiple angles → answer with citations</p>
          <div className="sugg-grid">
            {heroSugg.map((s) => (
              <button key={s.q} className="sugg" onClick={() => ask(s.q)}>
                <span className="sugg-icon">{s.icon}</span>
                <span className="sugg-text"><b>{s.label}</b><span>{s.q}</span></span>
                <span className="sugg-arrow">→</span>
              </button>
            ))}
          </div>
          <button className="shuffle-btn" onClick={() => setHeroSugg(pick4())}>🔀 Shuffle ideas</button>
          </div>
        )}

        <main className="thread">
          {messages.map((m, i) =>
            m.role === 'user' ? (
              <div key={i} className="fade-up">
                <h2 className="q-title">{m.content}</h2>
                {m.image && <div><img src={m.image} alt="query" style={{ maxWidth: 320, borderRadius: 12 }} /></div>}
                {m.queries?.length > 0 && (
                  <div className="pills">{m.queries.map((q) => <span key={q} className="pill">🔍 {q}</span>)}</div>
                )}
              </div>
            ) : (
              <div key={i} className="fade-up">
                {m.sources?.length > 0 && (
                  <>
                    <p className="researched">
                      <span className="dot-live" /> Researched {m.sources.length} sources across {m.queries?.length || 1} angle(s)
                    </p>
                    <div className="src-grid">
                      {m.sources.map((s) => (
                        <a key={s.n} className="src-card" href={s.url} target="_blank" rel="noreferrer">
                          <span className="src-num">{s.n}</span>
                          <span className="src-title">{s.title}</span>
                          <span className="src-domain"><img src={favicon(s.domain)} width="14" height="14" alt="" /> {s.domain}</span>
                        </a>
                      ))}
                    </div>
                  </>
                )}
                <div className="answer-card"><ReactMarkdown>{isNewestAnswer(i, m) ? m.content.slice(0, typed) + '▍' : m.content}</ReactMarkdown></div>
              </div>
            )
          )}
          {loading && (
            <div className="research-box pop-in">
              <div className="timeline">
                {STEPS.map((s, idx) => (
                  <div key={s} className={`t-step ${idx < stepIdx ? 'done' : idx === stepIdx ? 'active' : ''}`}>
                    <span className="t-dot">{idx < stepIdx ? '✓' : idx === stepIdx ? <span className="spinner" /> : '○'}</span>
                    {s}
                  </div>
                ))}
              </div>
              <div className="skeleton"><span /><span /><span className="short" /></div>
            </div>
          )}
          {error && <div className="error pop-in">{error}</div>}
          {!loading && messages.length > 0 && messages[messages.length - 1].role === 'assistant' &&
            (messages[messages.length - 1].sources?.length || 0) > 0 && (
              <div className="related pop-in">
                <p className="related-title">Related — keep exploring</p>
                <div className="rel-row">
                  {FOLLOW_UPS.map((f) => (
                    <button key={f} className="rel-chip" onClick={() => ask(`${f} (about: "${lastUserQ()}")`)}>
                      {f} →
                    </button>
                  ))}
                </div>
              </div>
            )}
          <div ref={bottomRef} />
        </main>

        <form
          className="askbar"
          onSubmit={(e) => {
            e.preventDefault()
            ask()
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything…"
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()} title="Send">{loading ? '…' : '➤'}</button>
        </form>
        <p className="footer">🔒 Key in your browser only · answers include citations — always verify important facts</p>
      </div>
    </div>
  )
}
