(function () {
  function $(id) { return document.getElementById(id); }
  function text(id, v) { const el = $(id); if (el) el.textContent = v; }
  function esc(s) { return String(s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

  const PLATFORM = {
    instagram: {
      label: "Instagram",
      gradient: "linear-gradient(135deg, #833ab4 0%, #fd1d1d 50%, #fcb045 100%)",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>',
    },
    facebook: {
      label: "Facebook",
      gradient: "linear-gradient(135deg, #1877F2 0%, #0d5fb8 100%)",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M22 12.06C22 6.5 17.52 2 12 2S2 6.5 2 12.06c0 5 3.66 9.13 8.44 9.88v-7H7.9v-2.88h2.54V9.85c0-2.5 1.49-3.88 3.77-3.88 1.09 0 2.24.19 2.24.19v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56v1.88h2.77l-.44 2.88h-2.33v7C18.34 21.19 22 17.06 22 12.06z"/></svg>',
    },
    tiktok: {
      label: "TikTok",
      gradient: "linear-gradient(135deg, #25F4EE 0%, #000 50%, #FE2C55 100%)",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-5.2 1.74 2.89 2.89 0 0 1 2.31-4.64 2.93 2.93 0 0 1 .88.13V9.4a6.84 6.84 0 0 0-1-.07A6.33 6.33 0 0 0 5.8 20.1a6.34 6.34 0 0 0 10.86-4.43V8.84a8.16 8.16 0 0 0 4.77 1.52V6.93a4.85 4.85 0 0 1-1.84-.24z"/></svg>',
    },
    youtube: {
      label: "YouTube",
      gradient: "linear-gradient(135deg, #FF0000 0%, #b80000 100%)",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2C0 8 0 12 0 12s0 4 .5 5.8a3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1C24 16 24 12 24 12s0-4-.5-5.8zM9.6 15.6V8.4l6.2 3.6-6.2 3.6z"/></svg>',
    },
  };

  const STATUS = {
    scheduled: { bg: "rgba(180, 130, 60, 0.12)", color: "var(--accent, #b48438)", dot: "#b48438", label: "Scheduled" },
    posted:    { bg: "rgba(16, 185, 129, 0.12)", color: "#10b981",                 dot: "#10b981", label: "Posted" },
    failed:    { bg: "rgba(239, 68, 68, 0.12)",  color: "#ef4444",                 dot: "#ef4444", label: "Failed" },
    pending:   { bg: "rgba(160, 160, 160, 0.12)", color: "#737373",                dot: "#737373", label: "Pending" },
  };

  let allPosts = [];
  let propertyImages = {};
  let currentFilter = "all";

  function relTime(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    const diff = (date - Date.now()) / 1000;
    const abs = Math.abs(diff);
    const fmt = (n, u) => `${Math.round(n)} ${u}${Math.round(n) === 1 ? "" : "s"}`;
    if (abs < 60) return diff >= 0 ? "in a moment" : "just now";
    if (abs < 3600) return diff >= 0 ? `in ${fmt(abs/60, "min")}` : `${fmt(abs/60, "min")} ago`;
    if (abs < 86400) return diff >= 0 ? `in ${fmt(abs/3600, "hr")}` : `${fmt(abs/3600, "hr")} ago`;
    if (abs < 86400 * 7) return diff >= 0 ? `in ${fmt(abs/86400, "day")}` : `${fmt(abs/86400, "day")} ago`;
    return date.toLocaleDateString();
  }

  function fmtAbs(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }

  function bucketFor(scheduledAt, status) {
    if (status === "posted") return { key: "posted", label: "Posted", order: 3 };
    if (status === "failed") return { key: "failed", label: "Needs attention", order: 4 };
    if (!scheduledAt) return { key: "unscheduled", label: "Unscheduled", order: 5 };
    const d = new Date(scheduledAt);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1);
    const dayAfter = new Date(today); dayAfter.setDate(dayAfter.getDate() + 2);
    const weekAhead = new Date(today); weekAhead.setDate(weekAhead.getDate() + 7);
    if (d >= today && d < tomorrow) return { key: "today", label: "Today", order: 0 };
    if (d >= tomorrow && d < dayAfter) return { key: "tomorrow", label: "Tomorrow", order: 1 };
    if (d >= today && d < weekAhead) return { key: "thisweek", label: "This week", order: 2 };
    if (d < today) return { key: "overdue", label: "Overdue", order: 6 };
    return { key: "later", label: "Later", order: 7 };
  }

  async function load() {
    let data;
    try {
      data = await yk.get("/agencies/me/social/");
    } catch (e) {
      $("yk-soc-list").innerHTML = `<div class="border border-red-500/30 bg-red-500/5 p-8 text-center text-sm" style="color:#ef4444">Failed to load: ${esc(e.message)}</div>`;
      return;
    }
    allPosts = Array.isArray(data) ? data : (data.results || []);

    const propIds = [...new Set(allPosts.map(p => p.propertyId).filter(Boolean))];
    propertyImages = {};
    if (propIds.length) {
      try {
        const myList = await yk.get("/agencies/me/listings/");
        for (const p of myList) propertyImages[p.id] = p.coverImageUrl || null;
      } catch {}
    }

    renderStats();
    render();
  }

  function renderStats() {
    const counts = allPosts.reduce((acc, p) => { acc[p.status] = (acc[p.status] || 0) + 1; return acc; }, {});
    text("yk-soc-total", allPosts.length);
    text("yk-soc-scheduled", counts.scheduled || 0);
    text("yk-soc-posted", counts.posted || 0);
    text("yk-soc-failed", counts.failed || 0);
    text("yk-soc-c-all", allPosts.length);
    text("yk-soc-c-scheduled", counts.scheduled || 0);
    text("yk-soc-c-posted", counts.posted || 0);
    text("yk-soc-c-failed", counts.failed || 0);
  }

  function postCard(p) {
    const platform = PLATFORM[p.platform] || { label: p.platform, gradient: "#888", icon: "" };
    const status = STATUS[p.status] || STATUS.pending;
    const cover = propertyImages[p.propertyId] || "/assets/property-1-BF0RFkF4.jpg";

    const action = p.postUrl
      ? `<a href="${esc(p.postUrl)}" target="_blank" rel="noopener" class="inline-flex items-center gap-1.5 bg-foreground/10 hover:bg-foreground/20 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-foreground transition-colors">View live<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M7 17L17 7M7 7h10v10"/></svg></a>`
      : p.status === "failed"
        ? `<button data-retry="${esc(p.id)}" class="yk-soc-retry inline-flex items-center gap-1.5 border border-border bg-background hover:bg-muted px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-foreground/80 transition-colors"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/></svg>Retry</button>`
        : `<div class="text-[10px] uppercase tracking-[0.18em] text-foreground/40">queued</div>`;

    const errorBlock = p.errorMessage
      ? `<div class="mt-3 border-l-2 px-3 py-2 text-xs leading-relaxed" style="border-color:#ef4444; background-color:rgba(239,68,68,0.05); color:#dc2626">${esc(p.errorMessage).slice(0, 240)}</div>`
      : "";

    const propTitle = p.propertyTitle || "Untitled listing";
    const propLink = p.propertyId
      ? `<a href="/properties/${esc(p.propertyId)}" class="font-medium text-foreground hover:text-accent transition-colors">${esc(propTitle)}</a>`
      : `<span class="font-medium text-foreground">${esc(propTitle)}</span>`;

    return `
      <article class="group border border-border bg-card hover:shadow-md transition-shadow overflow-hidden">
        <div class="flex items-stretch">
          <div class="w-24 lg:w-32 shrink-0 relative overflow-hidden" style="background-image: url('${esc(cover)}'); background-size: cover; background-position: center;">
            <div class="absolute inset-0" style="background: linear-gradient(135deg, rgba(0,0,0,0.1), rgba(0,0,0,0.5));"></div>
            <div class="absolute bottom-2 left-2 flex items-center gap-1.5 text-white">
              <div class="grid size-8 place-items-center text-white shadow-md" style="background:${platform.gradient}">${platform.icon}</div>
            </div>
          </div>
          <div class="flex-1 min-w-0 p-5">
            <div class="flex items-start justify-between gap-4 flex-wrap">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-[10px] font-bold uppercase tracking-[0.22em] text-foreground/60">${esc(platform.label)}</span>
                <span class="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em]" style="background:${status.bg}; color:${status.color}">
                  <span class="size-1.5 rounded-full" style="background:${status.dot}"></span>${esc(status.label)}
                </span>
              </div>
              ${action}
            </div>
            <div class="mt-2">${propLink}</div>
            <div class="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
              <span class="flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
                ${esc(fmtAbs(p.scheduledAt))}
              </span>
              <span class="flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
                ${esc(relTime(p.scheduledAt))}
              </span>
              ${p.postedAt ? `<span class="flex items-center gap-1.5" style="color:#10b981"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>${esc(fmtAbs(p.postedAt))}</span>` : ""}
            </div>
            ${errorBlock}
          </div>
        </div>
      </article>`;
  }

  function render() {
    const filtered = currentFilter === "all"
      ? allPosts
      : allPosts.filter(p => p.status === currentFilter);

    text("yk-soc-count", `${filtered.length} ${filtered.length === 1 ? "post" : "posts"}`);

    const list = $("yk-soc-list");
    if (!filtered.length) {
      list.innerHTML = `
        <div class="border border-dashed border-border bg-card/50 p-12 text-center">
          <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.25" class="mx-auto text-foreground/30"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
          <div class="mt-3 font-serif text-xl text-primary">No ${currentFilter === "all" ? "" : currentFilter + " "}posts yet</div>
          <div class="mt-2 text-sm text-muted-foreground">New listings auto-schedule posts on Instagram, Facebook, TikTok, and YouTube.</div>
        </div>`;
      return;
    }

    const groups = {};
    for (const p of filtered) {
      const b = bucketFor(p.scheduledAt, p.status);
      if (!groups[b.key]) groups[b.key] = { ...b, posts: [] };
      groups[b.key].posts.push(p);
    }

    const sortedGroups = Object.values(groups).sort((a, b) => a.order - b.order);
    list.innerHTML = sortedGroups.map(g => {
      const sortedPosts = [...g.posts].sort((a, b) => {
        const ad = new Date(a.scheduledAt || a.createdAt).getTime();
        const bd = new Date(b.scheduledAt || b.createdAt).getTime();
        return g.key === "posted" || g.key === "overdue" ? bd - ad : ad - bd;
      });
      return `
        <section>
          <div class="mb-3 flex items-center gap-3">
            <h2 class="font-serif text-2xl font-bold text-primary">${esc(g.label)}</h2>
            <div class="flex-1 h-px bg-border"></div>
            <span class="text-[10px] font-bold uppercase tracking-[0.22em] text-foreground/50">${g.posts.length} ${g.posts.length === 1 ? "post" : "posts"}</span>
          </div>
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            ${sortedPosts.map(postCard).join("")}
          </div>
        </section>`;
    }).join("");

    list.querySelectorAll(".yk-soc-retry").forEach(btn => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        const original = btn.innerHTML;
        btn.innerHTML = "Retrying…";
        alert("Use the admin retry action at /admin/social/socialpost/ — select the row → action dropdown → Retry publishing selected posts now.");
        btn.disabled = false;
        btn.innerHTML = original;
      });
    });
  }

  function wireFilters() {
    document.querySelectorAll(".yk-soc-filter").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".yk-soc-filter").forEach(b => {
          b.classList.remove("bg-accent", "text-white");
          b.classList.add("text-foreground/70");
        });
        btn.classList.add("bg-accent", "text-white");
        btn.classList.remove("text-foreground/70");
        currentFilter = btn.dataset.filter;
        render();
      });
    });
    const refresh = $("yk-soc-refresh");
    if (refresh) refresh.addEventListener("click", load);
  }

  yk.onReady(() => { wireFilters(); load(); });
})();
