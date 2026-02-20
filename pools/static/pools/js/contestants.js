// static/pools/js/contestants.js
(function () {
  "use strict";

  function onReady(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function debounce(fn, ms) {
    let t;
    return function () {
      clearTimeout(t);
      t = setTimeout(fn, ms);
    };
  }

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  function getContainedRect(imgEl) {
    // Rectangle where object-fit:contain actually draws (viewport px)
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    const natW = imgEl.naturalWidth || 1;
    const natH = imgEl.naturalHeight || 1;

    const scale = Math.min(vw / natW, vh / natH);
    const drawW = natW * scale;
    const drawH = natH * scale;

    const left = (vw - drawW) / 2;
    const top = (vh - drawH) / 2;

    return { left, top, width: drawW, height: drawH, scale };
  }

  function cssVarNumber(name, fallback) {
    const raw = getComputedStyle(document.documentElement).getPropertyValue(name);
    const v = parseFloat(String(raw).trim());
    return Number.isFinite(v) ? v : fallback;
  }

  function getPageFlipClass() {
    return (
      window.PageFlip ||
      (window.pageFlip && window.pageFlip.PageFlip) ||
      (window.St && window.St.PageFlip) ||
      (window.Page_Flip && window.Page_Flip.PageFlip) ||
      null
    );
  }

  // ----------------------------
  // Load field notes from static .txt
  // ----------------------------
  async function hydrateFieldNotes(BookEl) {
    const bios = BookEl.querySelectorAll('.bio[data-bio-url], .bio.bio-placeholder');
  
    for (const bioDiv of bios) {
      // Only hydrate placeholders
      const isPlaceholder = bioDiv.classList.contains("bio-placeholder") || !bioDiv.textContent.trim();
      if (!isPlaceholder) continue;
    
      // 1) Prefer explicit data-bio-url if present
      let url = bioDiv.getAttribute("data-bio-url");
    
      // 2) Otherwise infer from the portrait image filename (MOST robust)
      if (!url) {
        const page = bioDiv.closest(".page");
        const img = page ? page.querySelector(".portrait img") : null;
        const src = img ? img.getAttribute("src") : "";
      
        // Expect: /static/pools/cast/season-50/<filename>.(jpg/png/...)
        // Turn into: /static/pools/cast/season-50/bios/<filename>.txt
        if (src && src.includes("/pools/cast/season-50/")) {
          url = src
            .replace("/pools/cast/season-50/", "/pools/cast/season-50/bios/")
            .replace(/\.(jpe?g|png|webp)$/i, ".txt");
        }
      }
    
      if (!url) {
        bioDiv.textContent = "No field notes yet.";
        bioDiv.classList.add("bio-placeholder");
        continue;
      }
    
      try {
        // Important: encodeURI preserves slashes but safely encodes quotes etc.
        const res = await fetch(encodeURI(url), { cache: "no-cache" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
      
        const txt = (await res.text()).trim();
        if (txt.length) {
          bioDiv.classList.remove("bio-placeholder");
          bioDiv.innerHTML = txt.replace(/\n/g, "<br>");
        } else {
          bioDiv.textContent = "No field notes yet.";
          bioDiv.classList.add("bio-placeholder");
        }
      } catch (e) {
        bioDiv.textContent = "No field notes yet.";
        bioDiv.classList.add("bio-placeholder");
      }
    }
  }

  onReady(function () {
    const bg = document.getElementById("ctBg") || document.querySelector(".ct-bg");
    const overlay = document.getElementById("ctOverlay");
    const BookEl = document.getElementById("book");

    if (!bg || !overlay || !BookEl) return;

    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");

    // Base size must match CSS .book/.book-shell
    const BASE_W = 900;
    const BASE_H = 650;

    // Frame-fit targets (you are overriding these below with explicit targetW/targetH)
    // const TARGET_W_FRAC = 0.90;
    // const TARGET_H_FRAC = 0.70;

    function placeOverlay() {
      if (!bg.naturalWidth) return;

      const r = getContainedRect(bg);

      // Anchor point within contained image (0..1)
      const ax = clamp(cssVarNumber("--overlay-x", 0.50), 0, 1);
      const ay = clamp(cssVarNumber("--overlay-y", 0.58), 0, 1);

      // Put overlay at anchor point
      overlay.style.left = (r.left + r.width * ax) + "px";

      // Nudge down a bit to sit on notebook paper
      overlay.style.top  = (r.top + r.height * ay + r.height * 0.035) + "px";

      // How much of the background width/height the book should occupy
      const targetW = r.width  * 0.85;
      const targetH = r.height * 0.75;

      const sW = targetW / BASE_W;
      const sH = targetH / BASE_H;

      // Clamp keeps it stable across screen sizes
      const s = clamp(Math.min(sW, sH), 0.68, 1.35);
      overlay.style.setProperty("--ct-scale", s.toFixed(4));
    }

    const placeDebounced = debounce(placeOverlay, 70);

    if (bg.complete) placeOverlay();
    bg.addEventListener("load", placeOverlay);
    window.addEventListener("resize", placeDebounced);

    // Load notes ASAP (doesn't depend on PageFlip)
    hydrateFieldNotes(BookEl).catch(() => {});

    // PageFlip
    const PF = getPageFlipClass();
    if (!PF) {
      console.warn("PageFlip not found. Fallback paging enabled.");
      initFallbackPaging(BookEl, prevBtn, nextBtn);
      return;
    }

    let pageFlip;
    try {
      pageFlip = new PF(BookEl, {
        width: BASE_W,
        height: BASE_H,
        size: "fixed",
        autoSize: false,
        display: "double",

        minWidth: 320,
        maxWidth: 1600,
        minHeight: 360,
        maxHeight: 1800,

        drawShadow: true,
        maxShadowOpacity: 0.35,
        showCover: false,
        mobileScrollSupport: false,
        clickEventForward: true,
        useMouseEvents: true,
        useTouchEvents: true,
        flippingTime: 650,
        swipeDistance: 25,
        startZIndex: 0,
      });
    } catch (e) {
      console.error("PageFlip init failed:", e);
      initFallbackPaging(BookEl, prevBtn, nextBtn);
      return;
    }

    const pages = document.querySelectorAll("#book .page");
    try {
      pageFlip.loadFromHTML(pages);
    } catch (e) {
      console.warn("loadFromHTML failed, falling back:", e);
      initFallbackPaging(BookEl, prevBtn, nextBtn);
      return;
    }

    function safeUpdate() {
      try { pageFlip.update(); } catch (_) {}
      placeOverlay();
    }

    const relayout = debounce(safeUpdate, 80);
    window.addEventListener("resize", relayout);

    // Update after images load (and after notes load)
    const imgs = BookEl.querySelectorAll("img");
    let pending = imgs.length;

    if (pending) {
      imgs.forEach((img) => {
        if (img.complete) pending--;
        else img.addEventListener("load", () => {
          pending--;
          if (pending <= 0) safeUpdate();
        });
      });
      setTimeout(safeUpdate, 900);
    } else {
      setTimeout(safeUpdate, 150);
    }

    // Controls
    if (prevBtn) prevBtn.addEventListener("click", (e) => { e.preventDefault(); pageFlip.flipPrev(); });
    if (nextBtn) nextBtn.addEventListener("click", (e) => { e.preventDefault(); pageFlip.flipNext(); });

    document.addEventListener("keydown", function (e) {
      const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || (e.target && e.target.isContentEditable)) return;

      if (e.key === "ArrowLeft")  { e.preventDefault(); pageFlip.flipPrev(); }
      if (e.key === "ArrowRight") { e.preventDefault(); pageFlip.flipNext(); }
    });

    // Click edge paging – BUT allow catalog picking to intercept first
    BookEl.addEventListener("click", function (ev) {
      // If a pick handler already stopped propagation, don't flip.
      if (ev.defaultPrevented) return;

      const rect = BookEl.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const edge = rect.width * 0.18;

      if (x <= edge) pageFlip.flipPrev();
      else if (x >= rect.width - edge) pageFlip.flipNext();
    });

    // --- Catalog pick interaction (first-time entrants) ---
    try {
      const canPick = window.CATALOG_PICK && window.CATALOG_PICK.canPick;
      const joinCode = window.CATALOG_PICK && window.CATALOG_PICK.joinCode;

      if (canPick && joinCode) {
        const pageEls = BookEl.querySelectorAll('.page[data-contestant-id]');
        pageEls.forEach((p) => {
          p.style.cursor = 'pointer';

          p.addEventListener('click', (ev) => {
            // prevent flipping when picking
            ev.stopPropagation();
            ev.preventDefault();

            const cid = p.getAttribute('data-contestant-id');

            const pick = prompt('Set pick for this contestant. Type: first_out, winner_1, or winner_2');
            if (!pick) return;

            const pickType = pick.trim();
            if (!['first_out','winner_1','winner_2'].includes(pickType)){
              alert('Invalid pick type');
              return;
            }

            // get csrftoken
            const csrftoken = (function(){
              const name = 'csrftoken=';
              const ca = document.cookie.split(';');
              for(let i=0;i<ca.length;i++){
                let c=ca[i].trim();
                if(c.indexOf(name)===0) return decodeURIComponent(c.substring(name.length));
              }
              return null;
            })();

            fetch(`/pools/${joinCode}/catalog-pick/`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrftoken || ''
              },
              body: `pick_type=${encodeURIComponent(pickType)}&contestant_id=${encodeURIComponent(cid)}`
            })
            .then(r => r.json())
            .then((data) => {
              if (data && data.success) {
                alert(`Saved ${data.pick_type} → ${data.contestant}`);
                window.location.href = `/pools/${joinCode}/picks/`;
              } else {
                alert((data && data.error) || 'Save failed');
              }
            })
            .catch((err) => { console.error(err); alert('Network error'); });
          });
        });
      }
    } catch (e) {
      console.error('catalog-pick init failed', e);
    }
  });

  function initFallbackPaging(BookEl, prevBtn, nextBtn) {
    const pages = Array.from(BookEl.querySelectorAll(".page"));
    if (!pages.length) return;

    let idx = 0;
    pages.forEach((p, i) => { p.style.display = (i === idx) ? "block" : "none"; });

    function update() {
      pages.forEach((p, i) => { p.style.display = (i === idx) ? "block" : "none"; });
    }

    if (prevBtn) prevBtn.addEventListener("click", () => { idx = Math.max(0, idx - 1); update(); });
    if (nextBtn) nextBtn.addEventListener("click", () => { idx = Math.min(pages.length - 1, idx + 1); update(); });
  }
})();