(function () {
  function $(id) { return document.getElementById(id); }
  function text(id, v) { const el = $(id); if (el) el.textContent = v; }
  function html(id, v) { const el = $(id); if (el) el.innerHTML = v; }
  function esc(s) { return String(s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

  async function load() {
    let status = null, plans = [];
    try {
      [status, plans] = await Promise.all([
        yk.get("/subscriptions/status/").catch(() => null),
        yk.get("/subscriptions/plans/"),
      ]);
    } catch (e) {
      console.error("billing load failed", e);
      return;
    }
    plans = Array.isArray(plans) ? plans : (plans.results || []);

    renderCurrent(status);
    renderPlans(plans, status?.plan?.id);
  }

  function renderCurrent(sub) {
    if (!sub || !sub.plan) {
      text("yk-current-plan-name", "Free");
      text("yk-current-plan-price", "0 MAD / month");
      text("yk-current-plan-status", "No active paid subscription.");
      html("yk-current-plan-features", `<li class="text-muted-foreground">Basic listing management</li>`);
      $("yk-cancel-sub").classList.add("hidden");
      return;
    }
    const p = sub.plan;
    text("yk-current-plan-name", p.name);
    text("yk-current-plan-price", `${Number(p.priceMonthly).toLocaleString()} MAD / month`);
    const statusLine = sub.expiresAt
      ? `${sub.status} · renews ${new Date(sub.expiresAt).toLocaleDateString()}`
      : sub.status;
    text("yk-current-plan-status", statusLine);
    const flags = [
      p.hasAnalytics && "Analytics dashboard",
      p.hasLeadNotifications && "Lead notifications",
      p.hasSocialBoost && "Social media boost",
      p.maxListings ? `Up to ${p.maxListings} listings` : "Unlimited listings",
    ].filter(Boolean);
    html("yk-current-plan-features", flags.map(f => `<li>✓ ${esc(f)}</li>`).join(""));
    if (sub.stripeSubscriptionId) {
      $("yk-cancel-sub").classList.remove("hidden");
      $("yk-cancel-sub").onclick = async () => {
        if (!confirm("Cancel your subscription?")) return;
        try { await yk.post("/subscriptions/cancel/"); location.reload(); }
        catch (e) { alert("Cancel failed: " + e.message); }
      };
    }
  }

  function renderPlans(plans, currentPlanId) {
    if (!plans.length) {
      html("yk-plans-list", `<div class="text-sm opacity-70">No plans available right now.</div>`);
      return;
    }
    html("yk-plans-list", plans.map(p => {
      const isCurrent = p.id === currentPlanId;
      return `
        <div class="border border-white/10 p-4">
          <div class="flex items-baseline justify-between">
            <div class="font-serif text-xl font-bold">${esc(p.name)}</div>
            <div class="text-sm opacity-80">${Number(p.priceMonthly).toLocaleString()} MAD/mo</div>
          </div>
          ${p.description ? `<div class="mt-1 text-xs opacity-70">${esc(p.description)}</div>` : ""}
          ${isCurrent
            ? `<div class="mt-3 text-[10px] font-bold uppercase tracking-[0.18em] text-accent">Current plan</div>`
            : `<button data-plan="${esc(p.slug)}" class="yk-subscribe mt-3 w-full bg-accent py-2 text-[10px] font-bold uppercase tracking-[0.18em] text-white hover:bg-accent/80">Choose ${esc(p.name)}</button>`}
        </div>`;
    }).join(""));

    document.querySelectorAll(".yk-subscribe").forEach(btn => {
      btn.addEventListener("click", async () => {
        const slug = btn.dataset.plan;
        btn.disabled = true; btn.textContent = "Starting…";
        try {
          const res = await yk.post("/subscriptions/subscribe/", { planSlug: slug });
          if (res.checkoutUrl) location.href = res.checkoutUrl;
          else location.reload();
        } catch (e) {
          alert("Subscribe failed: " + (e.data?.detail || e.message));
          btn.disabled = false; btn.textContent = "Choose plan";
        }
      });
    });
  }

  yk.onReady(load);
})();
