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

  function channelBadge(channel) {
    const colorMap = {
      instagram: { bg: "linear-gradient(135deg,#833ab4,#fd1d1d,#fcb045)", color: "#fff" },
      facebook:  { bg: "#1877F2",                                         color: "#fff" },
      tiktok:    { bg: "linear-gradient(135deg,#25F4EE,#000,#FE2C55)",    color: "#fff" },
      youtube:   { bg: "#FF0000",                                          color: "#fff" },
      whatsapp:  { bg: "#25D366",                                          color: "#fff" },
      direct:    { bg: "rgba(127,127,127,0.15)",                           color: "#737373" },
    };
    const c = colorMap[channel] || colorMap.direct;
    return `<span class="inline-flex items-center px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em]" style="background:${c.bg};color:${c.color}">${esc(channel || "direct")}</span>`;
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

    const sourceCounts = leads.reduce((a, l) => { a[l.source] = (a[l.source] || 0) + 1; return a; }, {});
    text("yk-leads-total", leads.length);
    text("yk-leads-call", sourceCounts.call || 0);
    text("yk-leads-whatsapp", sourceCounts.whatsapp || 0);
    text("yk-leads-email", sourceCounts.email || 0);

    const channelCounts = leads.reduce((a, l) => {
      const c = l.channel || "direct";
      a[c] = (a[c] || 0) + 1;
      return a;
    }, {});

    const list = $("yk-leads-list");
    if (!leads.length) {
      list.innerHTML = `<div class="border border-dashed border-border p-10 text-center text-sm text-muted-foreground">No leads yet. They appear when a visitor clicks call/WhatsApp/email on one of your listings.</div>`;
      return;
    }

    const channelChips = Object.entries(channelCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([ch, n]) => `<div class="flex items-center gap-2 text-xs">${channelBadge(ch)} <span class="font-bold text-foreground">${n}</span></div>`)
      .join("");

    list.innerHTML = `
      <div class="mb-6 border border-border bg-card p-4">
        <div class="text-[10px] font-bold uppercase tracking-[0.22em] text-foreground/50 mb-3">Leads by channel</div>
        <div class="flex flex-wrap gap-4">${channelChips}</div>
      </div>
      <div class="space-y-3">
        ${leads.map(l => `
          <div class="border border-border bg-card p-4 flex items-center gap-4">
            <div class="flex-1 min-w-0">
              <div class="font-medium truncate">${esc(l.propertyTitle) || "Untitled listing"}</div>
              <div class="mt-1 text-xs text-muted-foreground">${esc(l.maskedPhone) || "—"} · ${relativeTime(l.createdAt)}</div>
              <div class="mt-2 flex items-center gap-2 flex-wrap">${channelBadge(l.channel || "direct")} <span class="text-[10px] text-muted-foreground">via</span> ${sourceBadge(l.source)}</div>
            </div>
            <a href="/properties/${esc(l.propertyId)}" class="text-[10px] font-bold uppercase tracking-[0.18em] text-accent hover:text-primary whitespace-nowrap">View listing →</a>
          </div>`).join("")}
      </div>`;
  }

  yk.onReady(load);
})();
