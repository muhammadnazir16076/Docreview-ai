import { useEffect, useRef, useState } from "react";
import {
  analyzeDocument,
  clearSession,
  deleteHistoryReport,
  downloadPdfReport,
  fetchHistory,
  fetchHistoryReport,
  fetchMe,
  getSavedUser,
  getToken,
  login,
  signup,
} from "./api.js";

const OK_TYPES = [".pdf", ".docx"];
const MAX_MB = 20;

function scoreColor(v) {
  return v >= 75 ? "var(--good)" : v >= 55 ? "var(--warn)" : "var(--bad)";
}

function AuthScreen({ onSuccess }) {
  const [mode, setMode] = useState("login"); // login | signup
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user =
        mode === "signup"
          ? await signup(name, email, password)
          : await login(email, password);
      onSuccess(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-card">
      <div className="tabs">
        <button
          type="button"
          className={mode === "login" ? "tab active" : "tab"}
          onClick={() => { setMode("login"); setError(""); }}
        >
          Login
        </button>
        <button
          type="button"
          className={mode === "signup" ? "tab active" : "tab"}
          onClick={() => { setMode("signup"); setError(""); }}
        >
          Create Account
        </button>
      </div>

      <form onSubmit={handleSubmit} className="auth-form">
        {mode === "signup" && (
          <label>
            Full Name
            <input
              type="text"
              required
              minLength={2}
              placeholder="e.g. Ayesha Khan"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
        )}
        <label>
          Email Address
          <input
            type="email"
            required
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            minLength={6}
            placeholder="Minimum 6 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        {error && <p className="err">{error}</p>}

        <button type="submit" disabled={loading}>
          {loading ? "Please wait..." : mode === "signup" ? "Create Account & Continue" : "Login"}
        </button>
      </form>
    </div>
  );
}

function Upload({ onFile, error }) {
  const input = useRef();
  const [drag, setDrag] = useState(false);
  return (
    <div
      className={"drop" + (drag ? " drag" : "")}
      onClick={() => input.current.click()}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); onFile(e.dataTransfer.files[0]); }}
    >
      <input
        ref={input}
        type="file"
        accept=".pdf,.docx"
        hidden
        onChange={(e) => onFile(e.target.files[0])}
      />
      <h2>Drop your document here</h2>
      <p>PDF (including scanned PDFs via OCR) or DOCX, up to {MAX_MB} MB. Click to browse.</p>
      {error && <p className="err">{error}</p>}
    </div>
  );
}

function HistoryList({ items, onOpen, onDelete }) {
  if (!items.length) {
    return (
      <div className="card center" style={{ marginTop: 20 }}>
        <p className="muted">No saved reviews yet. Upload a document to start your history.</p>
      </div>
    );
  }
  return (
    <div className="history-list">
      {items.map((item) => (
        <div key={item.id} className="card history-item">
          <div>
            <div className="history-title">
              <b>{item.filename}</b>
              {item.ocr_used ? <span className="pill ocr">OCR</span> : null}
            </div>
            <p className="muted small">
              {item.pages} pages · {item.word_count.toLocaleString()} words ·{" "}
              {new Date(item.created_at).toLocaleString()}
            </p>
          </div>
          <div className="history-right">
            <span className="score-badge" style={{ background: scoreColor(item.score) }}>
              {item.score}/100
            </span>
            <button onClick={() => onOpen(item.id)}>View Report</button>
            <button className="ghost danger" onClick={() => onDelete(item.id)}>Delete</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function Report({ r, onReset }) {
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [pdfErr, setPdfErr] = useState("");

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(r, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = r.filename + ".analysis.json";
    a.click();
  };

  const handlePdfDownload = async () => {
    setPdfErr("");
    setDownloadingPdf(true);
    try {
      await downloadPdfReport(r);
    } catch (e) {
      setPdfErr(e.message);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const cap = r.capitalization || { score: 100, totalIssues: 0, issues: [] };
  const gram = r.grammar || { score: 100, totalIssues: 0, issues: [] };
  const cit = r.citations || {
    score: 0,
    style: "None detected",
    inlineCount: 0,
    referenceCount: 0,
    hasReferenceSection: false,
    sampleCitations: [],
    unmatchedCitations: [],
  };

  return (
    <div className="report">
      <div className="row head">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <h2>{r.filename}</h2>
            {r.ocrUsed && <span className="pill ocr">Scanned PDF (OCR)</span>}
          </div>
          <p className="muted">
            {r.pages} pages · {r.wordCount.toLocaleString()} words
          </p>
          {pdfErr && <p className="err">{pdfErr}</p>}
        </div>
        <div className="actions">
          <button onClick={handlePdfDownload} disabled={downloadingPdf}>
            {downloadingPdf ? "Generating PDF..." : "Download PDF Report"}
          </button>
          <button className="ghost" onClick={downloadJson}>Download JSON</button>
          <button className="ghost" onClick={onReset}>New document</button>
        </div>
      </div>

      <div className="grid">
        <section className="card center">
          <div className="ring" style={{ "--v": r.score, "--c": scoreColor(r.score) }}>
            <span>{r.score}</span>
          </div>
          <p className="muted">Overall quality score</p>
        </section>

        <section className="card">
          <h3>Score breakdown</h3>
          {r.breakdown.map((b) => (
            <div key={b.label} className="bar">
              <span>{b.label}</span>
              <div><i style={{ width: b.value + "%", background: scoreColor(b.value) }} /></div>
              <b>{b.value}</b>
            </div>
          ))}
        </section>

        <section className="card wide">
          <h3>Summary</h3>
          <p>{r.summary}</p>
        </section>

        <section className="card">
          <h3>Sections detected</h3>
          <ul className="plain">
            {r.sections.map((s) => (
              <li key={s.name}>
                <span className={"dot " + (s.found ? "yes" : "no")} />
                {s.name} <em className="muted">{s.found ? "found" : "missing"}</em>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h3>Citation checker</h3>
          <div className="cit-stats">
            <div><span className="muted">Style</span><b>{cit.style}</b></div>
            <div><span className="muted">Inline Citations</span><b>{cit.inlineCount}</b></div>
            <div><span className="muted">References Found</span><b>{cit.referenceCount}</b></div>
          </div>
          {cit.sampleCitations.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <p className="muted small">Detected inline citations:</p>
              <div className="pill-wrap">
                {cit.sampleCitations.map((c, idx) => (
                  <span key={idx} className="pill">{c}</span>
                ))}
              </div>
            </div>
          )}
          {cit.unmatchedCitations.length > 0 && (
            <div className="warn-box">
              <b>Missing in References ({cit.unmatchedCitations.length}):</b>{" "}
              {cit.unmatchedCitations.join(", ")}
            </div>
          )}
          {cit.inlineCount === 0 && (
            <p className="muted small" style={{ marginTop: 8 }}>
              No inline citations (APA/Harvard or IEEE) found in body text.
            </p>
          )}
        </section>

        <section className="card">
          <h3>Capitalization check ({cap.totalIssues})</h3>
          {cap.issues.length === 0 ? (
            <p className="muted">No capitalization issues detected.</p>
          ) : (
            cap.issues.map((iss, idx) => (
              <div key={idx} className="issue-item">
                <span className="pill warn-pill">{iss.category}</span>
                <p className="small">{iss.snippet}</p>
                <p className="muted small">{iss.advice}</p>
              </div>
            ))
          )}
        </section>

        <section className="card">
          <h3>Grammar &amp; style check ({gram.totalIssues})</h3>
          {gram.issues.length === 0 ? (
            <p className="muted">No major grammar or style issues detected.</p>
          ) : (
            gram.issues.map((iss, idx) => (
              <div key={idx} className="issue-item">
                <span className="pill bad-pill">{iss.category}</span>
                <p className="small">{iss.snippet}</p>
                <p className="muted small">{iss.advice}</p>
              </div>
            ))
          )}
        </section>

        <section className="card wide">
          <h3>Repeated content</h3>
          {r.repeats.length === 0 && <p className="muted">No significant repetition found.</p>}
          {r.repeats.map((x, i) => (
            <div key={i} className="repeat">
              <b>{x.a} ↔ {x.b}</b> <span className="pill">{Math.round(x.similarity * 100)}% similar</span>
              <p className="muted">{x.text}</p>
            </div>
          ))}
        </section>

        <section className="card wide">
          <h3>Suggestions</h3>
          {r.suggestions.map((s, i) => (
            <div key={i} className="sugg">
              <span className={"tag " + s.type}>{s.type === "ai" ? "AI" : "Rule"}</span>
              <p>{s.text}</p>
            </div>
          ))}
        </section>
      </div>
      <p className="muted foot">This is a first-level review assistant, not a final authority.</p>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(() => getSavedUser());
  const [view, setView] = useState("upload"); // upload | loading | report | history
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) return;
    fetchMe()
      .then((u) => {
        setUser(u);
        loadHistory();
      })
      .catch(() => {
        clearSession();
        setUser(null);
      });
  }, []);

  async function loadHistory() {
    try {
      const items = await fetchHistory();
      setHistory(items);
    } catch {
      // ignore
    }
  }

  function handleAuthSuccess(u) {
    setUser(u);
    setView("upload");
    loadHistory();
  }

  function handleLogout() {
    clearSession();
    setUser(null);
    setResult(null);
    setHistory([]);
    setView("upload");
  }

  async function handleFile(file) {
    if (!file) return;
    setError("");
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!OK_TYPES.includes(ext)) return setError("Only PDF and DOCX files are supported.");
    if (file.size > MAX_MB * 1024 * 1024) return setError(`File is larger than ${MAX_MB} MB.`);
    setView("loading");
    try {
      const res = await analyzeDocument(file);
      setResult(res);
      setView("report");
      loadHistory();
    } catch (e) {
      setError(e.message);
      setView("upload");
    }
  }

  async function handleOpenHistory(id) {
    setError("");
    setView("loading");
    try {
      const res = await fetchHistoryReport(id);
      setResult(res);
      setView("report");
    } catch (e) {
      setError(e.message);
      setView("history");
    }
  }

  async function handleDeleteHistory(id) {
    try {
      await deleteHistoryReport(id);
      setHistory((prev) => prev.filter((item) => item.id !== id));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <main>
      <header className="topbar">
        <div>
          <h1>DocReview <span>AI</span></h1>
          <p>Grammar, capitalization, citation, OCR &amp; quality review before submission.</p>
        </div>
        {user && (
          <div className="user-nav">
            <button
              className={view === "upload" ? "" : "ghost"}
              onClick={() => { setError(""); setView("upload"); }}
            >
              New Review
            </button>
            <button
              className={view === "history" ? "" : "ghost"}
              onClick={() => { setError(""); loadHistory(); setView("history"); }}
            >
              My History ({history.length})
            </button>
            <span className="user-chip">{user.name}</span>
            <button className="ghost" onClick={handleLogout}>Logout</button>
          </div>
        )}
      </header>

      {!user && <AuthScreen onSuccess={handleAuthSuccess} />}

      {user && view === "upload" && <Upload onFile={handleFile} error={error} />}

      {user && view === "loading" && (
        <div className="drop">
          <div className="spin" />
          <h2>Analyzing document...</h2>
          <p>Running text/OCR extraction, grammar, capitalization, citation &amp; structure checks.</p>
        </div>
      )}

      {user && view === "history" && (
        <div style={{ marginTop: 20 }}>
          <h2>Your Saved Reviews</h2>
          {error && <p className="err">{error}</p>}
          <HistoryList
            items={history}
            onOpen={handleOpenHistory}
            onDelete={handleDeleteHistory}
          />
        </div>
      )}

      {user && view === "report" && result && (
        <Report r={result} onReset={() => setView("upload")} />
      )}
    </main>
  );
}
