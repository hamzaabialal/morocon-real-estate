(function () {
  function $(id) { return document.getElementById(id); }
  function text(id, value) { const el = $(id); if (el) el.textContent = value; }

  function initials(user, agency) {
    const first = (user?.firstName || user?.email || "?")[0];
    const last = (user?.lastName || agency?.name || "")[0] || "";
    return (first + last).toUpperCase();
  }

  async function init() {
    if (!window.yk || !yk.requireAuth()) return;
    const user = yk.getUser();
    let agency = user?.agency || null;
    if (!agency) {
      try { agency = await yk.get("/agencies/me/"); } catch { agency = null; }
    }
    text("yk-user-name", user ? `${user.firstName || ""} ${user.lastName || ""}`.trim() || user.email : "—");
    text("yk-agency-name", agency?.name || "—");
    text("yk-avatar", initials(user, agency));
    const logoutBtn = $("yk-logout");
    if (logoutBtn) logoutBtn.addEventListener("click", () => yk.logout());
    const detail = { user, agency };
    yk._chromeReady = detail;
    document.dispatchEvent(new CustomEvent("yk:chrome-ready", { detail }));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
