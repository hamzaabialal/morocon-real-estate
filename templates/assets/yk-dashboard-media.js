(function () {
  function $(id) { return document.getElementById(id); }
  function text(id, v) { const el = $(id); if (el) el.textContent = v; }
  function html(id, v) { const el = $(id); if (el) el.innerHTML = v; }
  function esc(s) { return String(s || "").replace(/[<>&"]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

  const STATUS = {
    ready:      { bg: "rgba(16, 185, 129, 0.12)", color: "#10b981", dot: "#10b981", label: "Ready" },
    generating: { bg: "rgba(180, 130, 60, 0.12)", color: "#b48438", dot: "#b48438", label: "Generating" },
    pending:    { bg: "rgba(160, 160, 160, 0.12)", color: "#737373", dot: "#737373", label: "Pending" },
    failed:     { bg: "rgba(239, 68, 68, 0.12)",  color: "#ef4444", dot: "#ef4444", label: "Failed" },
  };

  function fmtDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  }

  function statusPill(status) {
    const s = STATUS[status] || STATUS.pending;
    return `<span class="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em]" style="background:${s.bg};color:${s.color}">
      <span class="size-1.5 rounded-full" style="background:${s.dot}"></span>${esc(s.label)}
    </span>`;
  }

  async function load() {
    let listings = [];
    try {
      listings = await yk.get("/agencies/me/listings/");
    } catch (e) {
      html("yk-md-featured", `<div class="p-8 text-center text-sm" style="color:#ef4444">Failed to load: ${esc(e.message)}</div>`);
      html("yk-md-library", "");
      return;
    }

    renderStats(listings);
    renderFeatured(listings);
    renderLibrary(listings);
  }

  function renderStats(listings) {
    const counts = listings.reduce((acc, p) => { acc[p.mediaStatus] = (acc[p.mediaStatus] || 0) + 1; return acc; }, {});
    text("yk-md-total", listings.length);
    text("yk-md-ready", counts.ready || 0);
    text("yk-md-pending", (counts.pending || 0) + (counts.generating || 0));
    text("yk-md-failed", counts.failed || 0);
  }

  function renderFeatured(listings) {
    const ready = listings.filter(l => l.mediaStatus === "ready" && l.reelUrl);
    if (!ready.length) {
      html("yk-md-featured", `
        <div class="p-12 text-center">
          <div class="font-serif text-xl text-primary">No AI media generated yet</div>
          <div class="mt-2 text-sm text-muted-foreground">Create a listing and the AI Studio will produce a video + captions automatically.</div>
        </div>`);
      text("yk-md-featured-label", "—");
      return;
    }
    ready.sort((a, b) => new Date(b.mediaGeneratedAt || 0) - new Date(a.mediaGeneratedAt || 0));
    const f = ready[0];
    text("yk-md-featured-label", `generated ${fmtDate(f.mediaGeneratedAt)}`);
    const hashtagsHtml = (f.captionHashtags || []).slice(0, 12)
      .map(t => `<span class="inline-block bg-accent/10 text-accent px-2 py-1 text-[10px] font-bold tracking-wider mr-1 mb-1">${esc(t)}</span>`)
      .join("");
    html("yk-md-featured", `
      <div class="grid gap-0 lg:grid-cols-[360px_1fr]">
        <div class="bg-black grid place-items-center">
          <video controls muted playsinline preload="auto" style="aspect-ratio: 9/16; width: 100%; max-width: 360px; display: block;"
                 poster="${esc(f.coverImageUrl || '')}" src="${esc(f.reelUrl)}"></video>
        </div>
        <div class="p-6 lg:p-8 flex flex-col">
          <div class="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <div class="text-[10px] font-bold uppercase tracking-[0.22em] text-accent">Featured · ${esc(f.yakeeyRef || '')}</div>
              <h3 class="mt-1 font-serif text-2xl font-bold text-primary">${esc(f.title) || 'Untitled'}</h3>
            </div>
            ${statusPill(f.mediaStatus)}
          </div>

          <div class="mt-6">
            <div class="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.22em] text-foreground/50">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 8h14M5 12h14M5 16h14"/></svg>
              French caption
            </div>
            <div class="mt-2 text-sm leading-relaxed bg-muted/40 p-4 border-l-2 border-accent">${esc(f.captionFr || '(empty)')}</div>
          </div>

          <div class="mt-4">
            <div class="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.22em] text-foreground/50">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 8h14M5 12h14M5 16h14"/></svg>
              Arabic caption
            </div>
            <div dir="rtl" class="mt-2 text-sm leading-relaxed bg-muted/40 p-4 border-r-2 border-accent">${esc(f.captionAr || '(empty)')}</div>
          </div>

          ${hashtagsHtml ? `<div class="mt-4">
            <div class="text-[10px] font-bold uppercase tracking-[0.22em] text-foreground/50 mb-2">Hashtags · ${(f.captionHashtags || []).length}</div>
            <div>${hashtagsHtml}</div>
          </div>` : ''}

          <div class="mt-auto pt-6 flex items-center gap-3 flex-wrap">
            <a href="/properties/${esc(f.id)}" class="inline-flex items-center gap-2 bg-primary text-primary-foreground hover:bg-accent px-4 py-2 text-[11px] font-bold uppercase tracking-[0.18em]">View listing</a>
            <a href="${esc(f.reelUrl)}" target="_blank" class="inline-flex items-center gap-2 border border-border bg-card hover:bg-muted px-4 py-2 text-[11px] font-bold uppercase tracking-[0.18em]">Open MP4</a>
            ${f.squareVideoUrl ? `<a href="${esc(f.squareVideoUrl)}" target="_blank" class="inline-flex items-center gap-2 border border-border bg-card hover:bg-muted px-4 py-2 text-[11px] font-bold uppercase tracking-[0.18em]">Square version</a>` : ''}
            <button data-regen="${esc(f.id)}" class="yk-md-regen ml-auto inline-flex items-center gap-2 border border-accent text-accent hover:bg-accent hover:text-white px-4 py-2 text-[11px] font-bold uppercase tracking-[0.18em] transition-colors">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"/></svg>
              Regenerate
            </button>
          </div>
        </div>
      </div>`);
    wireRegenerateButtons();
  }

  function renderLibrary(listings) {
    text("yk-md-library-count", `${listings.length} ${listings.length === 1 ? "listing" : "listings"}`);
    const lib = $("yk-md-library");
    if (!listings.length) {
      lib.innerHTML = `<div class="col-span-full p-12 text-center text-sm text-muted-foreground">No listings yet.</div>`;
      return;
    }
    const sorted = [...listings].sort((a, b) => {
      const order = { ready: 0, generating: 1, pending: 2, failed: 3 };
      const oa = order[a.mediaStatus] ?? 9;
      const ob = order[b.mediaStatus] ?? 9;
      if (oa !== ob) return oa - ob;
      return new Date(b.mediaGeneratedAt || 0) - new Date(a.mediaGeneratedAt || 0);
    });
    lib.innerHTML = sorted.map(p => {
      const cover = p.coverImageUrl || "/assets/property-1-BF0RFkF4.jpg";
      const captionPreview = (p.captionFr || "").slice(0, 90) + (p.captionFr && p.captionFr.length > 90 ? "…" : "");
      const hashCount = (p.captionHashtags || []).length;
      const hasVideo = !!p.reelUrl;
      return `
        <article class="border border-border bg-card overflow-hidden hover:shadow-md transition-shadow flex flex-col">
          <a href="/properties/${esc(p.id)}" class="relative block overflow-hidden" style="aspect-ratio: 16/9;">
            <img src="${esc(cover)}" alt="${esc(p.title)}" class="size-full object-cover transition-transform group-hover:scale-105"/>
            <div class="absolute inset-0" style="background: linear-gradient(180deg, transparent 50%, rgba(0,0,0,0.6) 100%);"></div>
            <div class="absolute top-2 left-2">${statusPill(p.mediaStatus)}</div>
            ${hasVideo ? `<div class="absolute bottom-2 right-2 grid size-8 place-items-center bg-black/60 text-white">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M5 5a2 2 0 0 1 3-1.7l12 7a2 2 0 0 1 0 3.4l-12 7A2 2 0 0 1 5 19z"/></svg>
            </div>` : ''}
            <div class="absolute bottom-2 left-2 text-white">
              <div class="text-[10px] font-bold uppercase tracking-[0.18em] opacity-80">${esc(p.yakeeyRef || '')}</div>
              <div class="font-medium text-sm truncate max-w-[12rem]">${esc(p.title) || 'Untitled'}</div>
            </div>
          </a>
          <div class="p-4 flex-1 flex flex-col gap-3">
            ${captionPreview ? `<div class="text-xs leading-snug text-foreground/70">${esc(captionPreview)}</div>` : `<div class="text-xs text-muted-foreground italic">No caption yet</div>`}
            <div class="flex items-center justify-between mt-auto pt-2 border-t border-border">
              <div class="text-[10px] font-bold uppercase tracking-[0.18em] text-foreground/50">
                ${hashCount} hashtag${hashCount === 1 ? '' : 's'}${p.mediaGeneratedAt ? ' · ' + fmtDate(p.mediaGeneratedAt).split(',')[0] : ''}
              </div>
              <a href="/properties/${esc(p.id)}" class="text-[10px] font-bold uppercase tracking-[0.18em] text-accent hover:text-primary">Details →</a>
            </div>
            <button data-regen="${esc(p.id)}" class="yk-md-regen mt-1 inline-flex items-center justify-center gap-1.5 w-full border border-accent text-accent hover:bg-accent hover:text-white px-3 py-2 text-[10px] font-bold uppercase tracking-[0.18em] transition-colors">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/></svg>
              ${p.mediaStatus === 'ready' ? 'Regenerate AI' : 'Generate AI'}
            </button>
          </div>
        </article>`;
    }).join("");
    wireRegenerateButtons();
  }

  function wireRegenerateButtons() {
    document.querySelectorAll(".yk-md-regen:not(.yk-md-regen-wired)").forEach(btn => {
      btn.classList.add("yk-md-regen-wired");
      btn.addEventListener("click", async () => {
        const propId = btn.dataset.regen;
        const originalHtml = btn.innerHTML;
        const original = btn.cloneNode(true);
        btn.disabled = true;
        btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="animate-spin"><path d="M21 12a9 9 0 1 1-6.2-8.5"/></svg> Generating…`;
        btn.style.opacity = "0.7";
        try {
          const result = await yk.post(`/properties/${propId}/regenerate-media/`);
          if (result.status === "ready" || result.mediaStatus === "ready") {
            btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6L9 17l-5-5"/></svg> Done`;
            btn.style.background = "#10b981";
            btn.style.color = "white";
            btn.style.borderColor = "#10b981";
            setTimeout(() => load(), 700);
          } else {
            throw new Error(result.error || `status=${result.mediaStatus || result.status}`);
          }
        } catch (e) {
          btn.innerHTML = `Failed`;
          btn.style.background = "#ef4444";
          btn.style.color = "white";
          btn.style.borderColor = "#ef4444";
          alert(`Regeneration failed: ${e.message || e}`);
          setTimeout(() => { btn.innerHTML = originalHtml; btn.style = ""; btn.disabled = false; btn.classList.remove("yk-md-regen-wired"); }, 2500);
        }
      });
    });
  }

  yk.onReady(load);
})();
