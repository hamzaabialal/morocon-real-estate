(function () {
  function $(id) { return document.getElementById(id); }
  function text(id, v) { const el = $(id); if (el) el.textContent = v ?? "—"; }
  function esc(s) { return String(s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

  function getIdFromPath() {
    const m = location.pathname.match(/\/properties\/([0-9a-f-]{36})/i);
    return m ? m[1] : null;
  }

  function locationLine(p) {
    return [p.neighborhood, p.district, p.city].filter(Boolean).join(" · ") || "Morocco";
  }

  function showError(msg) {
    $("yk-pd-loading").classList.add("hidden");
    $("yk-pd-content").classList.add("hidden");
    const err = $("yk-pd-error");
    err.textContent = msg;
    err.classList.remove("hidden");
  }

  async function trackView(id) {
    try { await yk.post(`/properties/${id}/track_view/`, { referrer: document.referrer }); } catch {}
  }

  async function trackClick(id, kind) {
    try { await yk.post(`/properties/${id}/track_click/`, { click_type: kind }); } catch {}
  }

  async function load() {
    const id = getIdFromPath();
    if (!id) {
      showError("This page expects a UUID like /properties/<uuid>.");
      return;
    }
    let p;
    try {
      p = await yk.get(`/properties/${id}/`);
    } catch (e) {
      if (e.status === 404) showError("Property not found.");
      else showError("Failed to load property.");
      return;
    }

    $("yk-pd-loading").classList.add("hidden");
    $("yk-pd-content").classList.remove("hidden");

    const title = p.formattedAddress || `${p.propertyType || "Property"} ${p.yakeeyRef || ""}`.trim();
    document.title = `${title} — Yakeey`;
    text("yk-pd-name", title);
    text("yk-pd-location", locationLine(p));
    text("yk-pd-price", yk.fmtMAD(p.price));
    text("yk-pd-price2", yk.fmtMAD(p.price));
    text("yk-pd-transaction", p.transactionType || "");
    text("yk-pd-beds", p.bedrooms ?? "—");
    text("yk-pd-baths", p.bathrooms ?? "—");
    text("yk-pd-area", p.area ?? "—");
    text("yk-pd-type", p.propertyType || p.propertyCategory || "—");
    text("yk-pd-description", p.description || "No description provided.");
    text("yk-pd-reg", yk.fmtMAD(p.registrationFees));
    text("yk-pd-total", yk.fmtMAD(p.totalAcquisitionCost || p.price));
    text("yk-pd-ref", p.yakeeyRef || "—");
    text("yk-pd-listed", p.listedAt ? new Date(p.listedAt).toLocaleDateString() : "—");
    text("yk-pd-views", yk.fmtNumber(p.viewsCount ?? 0));
    text("yk-pd-status", p.status || "—");

    const img = $("yk-pd-cover");
    img.src = p.coverImageUrl || "/assets/property-1-BF0RFkF4.jpg";
    img.alt = title;

    text("yk-pd-agency-name", p.agency?.name || p.agentName || "Yakeey-listed");
    text("yk-pd-agency-meta", p.agency?.phone || p.agentPhone || "Contact via Yakeey");

    const phone = p.agency?.phone || p.agentPhone || "";
    const whatsapp = p.agency?.whatsapp || phone;
    const callBtn = $("yk-pd-call");
    const waBtn = $("yk-pd-whatsapp");
    if (phone) {
      callBtn.href = `tel:${phone}`;
      callBtn.addEventListener("click", () => trackClick(id, "call"));
    } else {
      callBtn.classList.add("opacity-50", "pointer-events-none");
    }
    if (whatsapp) {
      const cleaned = whatsapp.replace(/\D/g, "");
      const msg = encodeURIComponent(`Hi! I'm interested in your listing "${title}" on Yakeey.`);
      waBtn.href = `https://wa.me/${cleaned}?text=${msg}`;
      waBtn.addEventListener("click", () => trackClick(id, "whatsapp"));
    } else {
      waBtn.classList.add("opacity-50", "pointer-events-none");
    }

    trackView(id);
  }

  window.addEventListener("DOMContentLoaded", load);
})();
