(function () {
  function $(id) { return document.getElementById(id); }
  function text(id, value) { const el = $(id); if (el) el.textContent = value; }
  function html(id, value) { const el = $(id); if (el) el.innerHTML = value; }
  function esc(s) { return String(s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

  function fmtPct(n) {
    if (n == null) return "";
    const sign = n > 0 ? "+" : "";
    return `${sign}${n}%`;
  }

  let currentPeriod = "30d";

  async function load(period) {
    currentPeriod = period;
    try {
      const data = await yk.get(`/agencies/me/analytics/?period=${period}`);
      renderStats(data.summary || {});
      renderDailyChart(data.dailyViews || []);
      renderTopListings(data.topListings || []);
      renderSource(data.bySource || {});
    } catch (e) {
      console.error("analytics load failed", e);
    }
  }

  function renderStats(s) {
    text("yk-an-views", yk.fmtNumber(s.totalViews ?? 0));
    text("yk-an-views-sub", fmtPct(s.viewsChangePct));
    text("yk-an-clicks", yk.fmtNumber(s.totalClicks ?? 0));
    text("yk-an-clicks-sub", fmtPct(s.clicksChangePct));
    const ctr = s.totalViews ? ((s.totalClicks / s.totalViews) * 100).toFixed(1) + "%" : "—";
    text("yk-an-ctr", ctr);
    text("yk-an-leads", yk.fmtNumber(s.totalLeads ?? 0));
    text("yk-an-leads-sub", `${s.totalLeads ?? 0} this period`);
  }

  function renderDailyChart(daily) {
    const el = $("yk-an-chart-daily");
    if (!el) return;
    if (!daily.length) { el.innerHTML = `<div class="text-sm text-muted-foreground">No data yet.</div>`; return; }
    const w = 600, h = 250, pad = 30;
    const maxV = Math.max(1, ...daily.map(d => Math.max(d.views, d.clicks)));
    const sx = (i) => pad + (i / Math.max(1, daily.length - 1)) * (w - pad * 2);
    const sy = (v) => h - pad - (v / maxV) * (h - pad * 2);
    const pathV = daily.map((d, i) => `${i === 0 ? "M" : "L"}${sx(i)},${sy(d.views)}`).join(" ");
    const pathC = daily.map((d, i) => `${i === 0 ? "M" : "L"}${sx(i)},${sy(d.clicks)}`).join(" ");
    el.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:100%">
        <path d="${pathV}" fill="none" stroke="oklch(34% .07 165)" stroke-width="2"/>
        <path d="${pathC}" fill="none" stroke="oklch(62% .13 55)" stroke-width="2"/>
        <text x="${pad}" y="${pad - 8}" font-size="10" fill="currentColor" opacity="0.5">peak: ${maxV}</text>
      </svg>
      <div class="mt-2 flex gap-4 text-[10px] uppercase tracking-[0.18em] text-foreground/60">
        <span><span style="display:inline-block;width:8px;height:8px;background:oklch(34% .07 165);margin-right:4px"></span>Views</span>
        <span><span style="display:inline-block;width:8px;height:8px;background:oklch(62% .13 55);margin-right:4px"></span>Clicks</span>
      </div>`;
  }

  function renderTopListings(items) {
    const el = $("yk-an-top-listings");
    if (!el) return;
    if (!items.length) { el.innerHTML = `<div class="text-sm text-muted-foreground">No listings have views yet.</div>`; return; }
    el.innerHTML = `<ul class="divide-y divide-border">${items.map(l => `
      <li class="flex items-center gap-3 py-3">
        <div class="flex-1 min-w-0">
          <div class="font-medium truncate text-sm">${esc(l.title) || "Untitled"}</div>
          <div class="text-xs text-muted-foreground">${l.views || 0} views · ${l.clicks || 0} clicks</div>
        </div>
      </li>`).join("")}</ul>`;
  }

  function renderSource(by) {
    const el = $("yk-an-source");
    if (!el) return;
    const entries = Object.entries(by).filter(([_, v]) => v > 0).sort((a, b) => b[1] - a[1]);
    const total = entries.reduce((s, [_, v]) => s + v, 0);
    if (!total) { el.innerHTML = `<div class="text-sm text-muted-foreground">No traffic yet.</div>`; return; }
    el.innerHTML = entries.map(([src, n]) => {
      const pct = ((n / total) * 100).toFixed(1);
      return `<div>
        <div class="flex justify-between text-xs"><span class="font-medium capitalize">${esc(src)}</span><span class="text-muted-foreground">${n} (${pct}%)</span></div>
        <div class="mt-1 h-1.5 w-full bg-muted overflow-hidden"><div class="h-full bg-accent" style="width:${pct}%"></div></div>
      </div>`;
    }).join("");
  }

  function wirePeriodButtons() {
    document.querySelectorAll(".yk-period").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".yk-period").forEach(b => {
          b.classList.remove("bg-accent", "text-white");
          b.classList.add("bg-card");
        });
        btn.classList.add("bg-accent", "text-white");
        btn.classList.remove("bg-card");
        load(btn.dataset.period);
      });
    });
  }

  yk.onReady(() => {
    wirePeriodButtons();
    load(currentPeriod);
  });
})();
