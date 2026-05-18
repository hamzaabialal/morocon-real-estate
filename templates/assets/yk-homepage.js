(function () {
  function $(id) { return document.getElementById(id); }
  function text(id, v) { const el = $(id); if (el) el.textContent = v; }

  async function load() {
    let stats = null, agencyResp = null;
    try {
      [stats, agencyResp] = await Promise.all([
        yk.get("/stats/market/").catch(() => null),
        yk.get("/agencies/").catch(() => null),
      ]);
    } catch {}

    const totalListings = stats?.totalListings ?? 0;
    const agencyCount = agencyResp?.count ?? (Array.isArray(agencyResp) ? agencyResp.length : 0);

    text("yk-hp-agencies", agencyCount > 0 ? `+${yk.fmtNumber(agencyCount)}` : "+240");
    text("yk-hp-listings", totalListings > 0 ? yk.fmtNumber(totalListings) : "18K");
    text("yk-hp-footer-listings", yk.fmtNumber(Math.max(totalListings, 0)));
  }

  window.addEventListener("DOMContentLoaded", load);
})();
