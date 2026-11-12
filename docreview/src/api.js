const TOKEN_KEY = "docreview_token";
const USER_KEY = "docreview_user";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function getSavedUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

export function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}`, ...extra } : { ...extra };
}

async function handleResponse(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export async function signup(name, email, password) {
  const res = await fetch("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });
  const data = await handleResponse(res);
  saveSession(data.token, data.user);
  return data.user;
}

export async function login(email, password) {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await handleResponse(res);
  saveSession(data.token, data.user);
  return data.user;
}

export async function fetchMe() {
  const res = await fetch("/api/auth/me", { headers: authHeaders() });
  const data = await handleResponse(res);
  return data.user;
}

export async function analyzeDocument(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  return handleResponse(res);
}

export async function fetchHistory() {
  const res = await fetch("/api/history", { headers: authHeaders() });
  const data = await handleResponse(res);
  return data.items || [];
}

export async function fetchHistoryReport(id) {
  const res = await fetch(`/api/history/${id}`, { headers: authHeaders() });
  return handleResponse(res);
}

export async function deleteHistoryReport(id) {
  const res = await fetch(`/api/history/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handleResponse(res);
}

export async function downloadPdfReport(report) {
  const url = report.id ? `/api/history/${report.id}/pdf` : "/api/report/pdf";
  const opts = report.id
    ? { method: "GET", headers: authHeaders() }
    : {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(report),
      };

  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Could not generate PDF report");
  }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  const base = (report.filename || "document").replace(/\.[^.]+$/, "");
  a.download = `${base}_review_report.pdf`;
  a.click();
  URL.revokeObjectURL(a.href);
}
