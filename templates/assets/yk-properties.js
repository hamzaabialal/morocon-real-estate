(function () {
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

  let timer = null;

  function debounce(fn, ms) { return (...a) => { clearTimeout(timer); timer = setTimeout(() => fn(...a), ms); }; }

  function locationLine(p) {
    const parts = [p.neighborhood, p.city].filter(Boolean);
    return parts.join(" · ") || "Morocco";
  }

  function cardHtml(p) {
    const img = p.coverImageUrl || "/assets/property-1-BF0RFkF4.jpg";
    const title = p.formattedAddress || `${p.propertyType || "Property"} ${p.yakeeyRef || ""}`.trim();
    return `<a href="/properties/${esc(p.id)}" class="group block bg-card hairline transition-all duration-500 hover:-translate-y-1">
      <div class="relative aspect-[4/5] overflow-hidden bg-muted">
        <img src="${esc(img)}" alt="${esc(title)}" loading="lazy" class="size-full object-cover transition-transform duration-700 group-hover:scale-105"/>
        <div class="absolute inset-0 bg-gradient-to-t from-primary/80 via-primary/0 to-primary/0"></div>
        ${p.isFeatured ? '<div class="absolute left-3 top-3 bg-accent px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.18em] text-white">Featured</div>' : ''}
        <div class="absolute inset-x-0 bottom-0 p-5 text-sand">
          <div class="text-[10px] font-bold uppercase tracking-[0.18em] opacity-80">${esc(locationLine(p))}</div>
          <div class="mt-1 font-serif text-xl font-bold leading-tight">${esc(title)}</div>
          <div class="mt-1 text-base font-semibold">${yk.fmtMAD(p.price)}</div>
        </div>
      </div>
      <div class="flex items-center justify-between border-t border-border px-5 py-4 text-xs text-muted-foreground">
        <span>${p.bedrooms || 0} bed</span>
        <span>${p.bathrooms || 0} bath</span>
        <span>${p.area || 0} m²</span>
        <span class="font-bold text-foreground/80 capitalize">${esc(p.propertyType || p.propertyCategory || "")}</span>
      </div>
    </a>`;
  }

  async function load() {
    const params = new URLSearchParams();
    const q = $("yk-prop-search")?.value.trim();
    const city = $("yk-prop-city")?.value;
    const type = $("yk-prop-type")?.value;
    if (q) params.set("search", q);
    if (city) params.set("city", city);
    if (type) params.set("property_type", type);
    params.set("status", "LISTED");

    const grid = $("yk-properties-grid");
    grid.innerHTML = '<div class="col-span-full text-center text-sm text-muted-foreground py-20">Loading…</div>';

    let data;
    try {
      data = await yk.get(`/properties/?${params}`);
    } catch (e) {
      grid.innerHTML = `<div class="col-span-full text-center text-sm py-20" style="color:#ef4444">Failed to load listings.</div>`;
      return;
    }
    const results = Array.isArray(data) ? data : (data.results || []);
    const total = data.count ?? results.length;
    $("yk-properties-count").textContent = total;

    if (!results.length) {
      grid.innerHTML = '<div class="col-span-full text-center text-sm text-muted-foreground py-20">No listings match these filters yet.</div>';
      return;
    }
    grid.innerHTML = results.map(cardHtml).join("");
  }

  function wireFilters() {
    const search = $("yk-prop-search");
    const city = $("yk-prop-city");
    const type = $("yk-prop-type");
    if (search) search.addEventListener("input", debounce(load, 300));
    if (city) city.addEventListener("change", load);
    if (type) type.addEventListener("change", load);
  }

  window.addEventListener("DOMContentLoaded", () => { wireFilters(); load(); });
})();
