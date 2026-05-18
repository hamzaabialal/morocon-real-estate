(function () {
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

  function statusBadge(status) {
    const colors = {
      LISTED: "bg-accent/15 text-accent",
      SOLD: "bg-green-500/15 text-green-700",
      RENTED: "bg-blue-500/15 text-blue-700",
      ARCHIVED: "bg-muted text-muted-foreground",
    };
    return `<span class="px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${colors[status] || 'bg-muted text-muted-foreground'}">${esc(status)}</span>`;
  }

  async function loadListings() {
    let listings = [];
    try {
      listings = await yk.get("/agencies/me/listings/");
    } catch (e) {
      console.error("listings load failed", e);
      $("yk-listings-tbody").innerHTML = `<tr><td colspan="7" class="px-5 py-8 text-center text-sm" style="color:#ef4444">Failed to load listings.</td></tr>`;
      return;
    }

    const active = listings.filter(l => l.status === "LISTED").length;
    $("yk-listings-count").textContent = active;

    const tbody = $("yk-listings-tbody");
    if (!listings.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="px-5 py-10 text-center text-sm text-muted-foreground">No listings yet. Click <strong>+ New listing</strong> to add your first one.</td></tr>`;
      return;
    }
    tbody.innerHTML = listings.map(l => `
      <tr class="border-b border-border hover:bg-muted/50">
        <td class="px-5 py-4">
          <div class="font-medium truncate max-w-xs">${esc(l.title) || "Untitled"}</div>
          <div class="text-xs text-muted-foreground">Ref: ${esc(l.yakeeyRef) || "—"}</div>
        </td>
        <td class="px-5 py-4">${statusBadge(l.status)}</td>
        <td class="px-5 py-4 text-right font-semibold whitespace-nowrap">${yk.fmtMAD(l.price)}</td>
        <td class="px-5 py-4 text-right">${yk.fmtNumber(l.viewsCount)}</td>
        <td class="px-5 py-4 text-right">${yk.fmtNumber(l.clicksCount)}</td>
        <td class="px-5 py-4 text-right text-muted-foreground">${l.daysListed ?? "—"}d</td>
        <td class="px-5 py-4 text-right"><a href="/properties/${esc(l.id)}" class="text-[10px] font-bold uppercase tracking-[0.18em] text-accent hover:text-primary">View →</a></td>
      </tr>`).join("");
  }

  async function loadCities() {
    const select = $("yk-form-city");
    if (!select) return;
    try {
      const data = await yk.get("/locations/cities/");
      const cities = Array.isArray(data) ? data : (data.results || []);
      if (!cities.length) {
        select.innerHTML = `<option value="">No cities configured</option>`;
        return;
      }
      select.innerHTML = `<option value="">Select a city…</option>` + cities
        .map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`)
        .join("");
    } catch (e) {
      select.innerHTML = `<option value="">Failed to load cities</option>`;
    }
  }

  function openModal() {
    $("yk-new-listing-modal").classList.remove("hidden");
  }

  function closeModal() {
    $("yk-new-listing-modal").classList.add("hidden");
    $("yk-new-listing-form").reset();
    $("yk-form-err").classList.add("hidden");
  }

  function formatError(err) {
    const data = err.data;
    if (!data) return err.message || "Request failed";
    if (typeof data === "string") return data;
    if (data.detail) return data.detail;
    const entries = Object.entries(data);
    if (!entries.length) return err.message || "Request failed";
    const [field, msgs] = entries[0];
    return `${field}: ${Array.isArray(msgs) ? msgs[0] : msgs}`;
  }

  function wireForm() {
    const open = $("yk-new-listing");
    const close = $("yk-new-listing-close");
    const cancel = $("yk-form-cancel");
    const form = $("yk-new-listing-form");
    const errEl = $("yk-form-err");
    const submit = $("yk-form-submit");

    if (open) open.addEventListener("click", openModal);
    if (close) close.addEventListener("click", closeModal);
    if (cancel) cancel.addEventListener("click", closeModal);

    if (!form) return;
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errEl.classList.add("hidden");
      submit.disabled = true; submit.textContent = "Creating…";

      const fd = new FormData(form);
      const payload = {};
      for (const [k, v] of fd.entries()) {
        if (v === "" || v == null) continue;
        payload[k] = v;
      }
      for (const numField of ["price", "area", "bedrooms", "bathrooms"]) {
        if (payload[numField] != null) payload[numField] = Number(payload[numField]);
      }

      try {
        await yk.post("/properties/", payload);
        closeModal();
        await loadListings();
      } catch (ex) {
        errEl.textContent = formatError(ex);
        errEl.classList.remove("hidden");
      } finally {
        submit.disabled = false; submit.textContent = "Create listing";
      }
    });
  }

  yk.onReady(() => {
    wireForm();
    loadCities();
    loadListings();
  });
})();
