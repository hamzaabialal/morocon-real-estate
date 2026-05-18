(function (root) {
  const BASE = "/api/v1";
  const TOKEN_KEY = "yk_access";
  const REFRESH_KEY = "yk_refresh";
  const USER_KEY = "yk_user";

  function storeAuth(data) {
    if (data.access) localStorage.setItem(TOKEN_KEY, data.access);
    if (data.refresh) localStorage.setItem(REFRESH_KEY, data.refresh);
    if (data.user) localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  }

  function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function getUser() {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  }

  async function api(method, path, body) {
    const headers = { Accept: "application/json" };
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers.Authorization = `Bearer ${token}`;
    const opts = { method, headers };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(BASE + path, opts);
    if (res.status === 401) {
      clearAuth();
      if (!location.pathname.startsWith("/login")) location.href = "/login";
      throw new Error("unauthorized");
    }
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) {
      const err = new Error(data?.detail || data?.error || `HTTP ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  async function login(email, password) {
    const data = await api("POST", "/auth/login/", { email, password });
    storeAuth(data);
    return data;
  }

  async function register(payload) {
    const data = await api("POST", "/auth/register/", payload);
    storeAuth(data);
    return data;
  }

  async function logout() {
    const refresh = localStorage.getItem(REFRESH_KEY);
    try { if (refresh) await api("POST", "/auth/logout/", { refresh }); } catch (e) {}
    clearAuth();
    location.href = "/";
  }

  function requireAuth() {
    if (!localStorage.getItem(TOKEN_KEY)) {
      const next = encodeURIComponent(location.pathname + location.search);
      location.href = `/login?next=${next}`;
      return false;
    }
    return true;
  }

  function isAuthed() { return !!localStorage.getItem(TOKEN_KEY); }

  function fmtMAD(n) {
    if (n == null) return "—";
    return new Intl.NumberFormat("fr-MA", { maximumFractionDigits: 0 }).format(n) + " MAD";
  }

  function fmtNumber(n) {
    if (n == null) return "—";
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, "") + "K";
    return String(n);
  }

  function onReady(callback) {
    if (root.yk && root.yk._chromeReady) {
      callback(root.yk._chromeReady);
    } else {
      document.addEventListener("yk:chrome-ready", (event) => callback(event.detail), { once: true });
    }
  }

  root.yk = {
    api,
    get: (p) => api("GET", p),
    post: (p, b) => api("POST", p, b),
    patch: (p, b) => api("PATCH", p, b),
    del: (p) => api("DELETE", p),
    login,
    register,
    logout,
    requireAuth,
    isAuthed,
    getUser,
    storeAuth,
    clearAuth,
    fmtMAD,
    fmtNumber,
    onReady,
    _chromeReady: null,
  };
})(window);
