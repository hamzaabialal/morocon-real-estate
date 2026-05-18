(function () {
  function $(id) { return document.getElementById(id); }
  function text(id, value) { const el = $(id); if (el) el.textContent = value; }

  function fmtPct(n) {
    if (n == null) return "";
    const sign = n > 0 ? "+" : "";
    return `${sign}${n}%`;
  }

  function escapeHtml(s) {
    return String(s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));
  }

  async function loadStats() {
    let analytics = null, listings = [];
    try {
      [analytics, listings] = await Promise.all([
        yk.get("/agencies/me/analytics/?period=30d"),
        yk.get("/agencies/me/listings/"),
      ]);
    } catch (e) {
      console.error("dashboard data load failed", e);
      return;
    }

    const activeListings = listings.filter(l => l.status === "LISTED");
    const pipelineValue = activeListings.reduce((sum, l) => sum + Number(l.price || 0), 0);
    text("yk-stat-pipeline", yk.fmtMAD(pipelineValue));
    text("yk-stat-pipeline-sub", `${activeListings.length} active listing${activeListings.length === 1 ? "" : "s"}`);

    const summary = analytics?.summary || {};
    text("yk-stat-views", yk.fmtNumber(summary.totalViews ?? 0));
    text("yk-stat-views-sub", fmtPct(summary.viewsChangePct) || "—");
    text("yk-stat-leads", yk.fmtNumber(summary.totalLeads ?? 0));
    text("yk-stat-leads-sub", `${summary.totalLeads ?? 0} this period`);
    text("yk-stat-clicks", yk.fmtNumber(summary.totalClicks ?? 0));
    text("yk-stat-clicks-sub", fmtPct(summary.clicksChangePct) || "—");

    renderRecentListings(listings);
  }

  function renderRecentListings(listings) {
    const ul = $("yk-recent-listings");
    if (!ul) return;
    if (!listings.length) {
      ul.innerHTML = `<li class="py-4 text-sm text-muted-foreground">No listings yet. <a href="/dashboard/listings" class="text-accent underline">Add your first one →</a></li>`;
      return;
    }
    const recent = [...listings]
      .sort((a, b) => (b.viewsCount || 0) - (a.viewsCount || 0))
      .slice(0, 5);
    ul.innerHTML = recent.map(l => `
      <li class="flex items-center gap-4 py-3">
        <div class="grid size-12 place-items-center bg-muted text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">${escapeHtml((l.yakeeyRef || "—").slice(0, 4))}</div>
        <div class="flex-1 min-w-0">
          <div class="font-medium truncate">${escapeHtml(l.title) || "Untitled listing"}</div>
          <div class="text-xs text-muted-foreground">${l.viewsCount || 0} views · ${l.clicksCount || 0} clicks · ${l.daysListed ?? 0}d</div>
        </div>
        <div class="text-sm font-semibold whitespace-nowrap">${yk.fmtMAD(l.price)}</div>
        <span class="bg-accent/15 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em] text-accent">${escapeHtml(l.status)}</span>
      </li>`).join("");
  }

  yk.onReady(loadStats);
})();
