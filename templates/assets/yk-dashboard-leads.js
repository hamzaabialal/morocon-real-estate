(function () {
  function $(id) { return document.getElementById(id); }
  function text(id, v) { const el = $(id); if (el) el.textContent = v; }
  function esc(s) { return String(s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

  function relativeTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return Math.floor(diff / 60) + "m ago";
    if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
    if (diff < 86400 * 7) return Math.floor(diff / 86400) + "d ago";
    return d.toLocaleDateString();
  }

  function sourceBadge(source) {
    const colors = {
      call: "bg-accent/15 text-accent",
      whatsapp: "bg-green-500/15 text-green-700",
      email: "bg-blue-500/15 text-blue-700",
    };
    return `<span class="px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${colors[source] || 'bg-muted text-muted-foreground'}">${esc(source)}</span>`;
  }

  async function load() {
    let leads = [];
    try {
      const data = await yk.get("/agencies/me/leads/");
      leads = Array.isArray(data) ? data : (data.results || []);
    } catch (e) {
      console.error("leads load failed", e);
      $("yk-leads-list").innerHTML = `<div class="text-sm" style="color:#ef4444">Failed to load leads.</div>`;
      return;
    }

    const counts = leads.reduce((a, l) => { a[l.source] = (a[l.source] || 0) + 1; return a; }, {});
    text("yk-leads-total", leads.length);
    text("yk-leads-call", counts.call || 0);
    text("yk-leads-whatsapp", counts.whatsapp || 0);
    text("yk-leads-email", counts.email || 0);

    const list = $("yk-leads-list");
    if (!leads.length) {
      list.innerHTML = `<div class="border border-dashed border-border p-10 text-center text-sm text-muted-foreground">No leads yet. They appear when a visitor clicks call/WhatsApp/email on one of your listings.</div>`;
      return;
    }
    list.innerHTML = leads.map(l => `
      <div class="border border-border bg-card p-4 flex items-center gap-4">
        <div class="flex-1 min-w-0">
          <div class="font-medium truncate">${esc(l.propertyTitle) || "Untitled listing"}</div>
          <div class="mt-1 text-xs text-muted-foreground">Lead phone: ${esc(l.maskedPhone) || "—"} · ${relativeTime(l.createdAt)}</div>
        </div>
        ${sourceBadge(l.source)}
        <a href="/properties/${esc(l.propertyId)}" class="text-[10px] font-bold uppercase tracking-[0.18em] text-accent hover:text-primary">View listing →</a>
      </div>`).join("");
  }

  yk.onReady(load);
})();
