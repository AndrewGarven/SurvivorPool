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

  function getContainedRect(imgEl) {
    // returns the rectangle (in viewport px) where the object-fit:contain image actually draws
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    const natW = imgEl.naturalWidth || 1;
    const natH = imgEl.naturalHeight || 1;

    const scale = Math.min(vw / natW, vh / natH);
    const drawW = natW * scale;
    const drawH = natH * scale;

    const left = (vw - drawW) / 2;
    const top = (vh - drawH) / 2;

    return { left, top, width: drawW, height: drawH };
  }

  // ----------------------------
  // Load field notes from static .txt
  // Expects: .bio[data-bio="1"][data-bio-url="..."]
  // ----------------------------
  async function hydrateFieldNotes(BookEl) {
    const bios = BookEl.querySelectorAll('.bio[data-bio="1"][data-bio-url]');
    for (const el of bios) {
      const url = el.getAttribute("data-bio-url");
      if (!url) continue;

      try {
        const res = await fetch(url, { cache: "no-cache" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const txt = (await res.text()).trim();

        if (txt.length) {
          el.classList.remove("bio-placeholder");
          // Preserve newlines
          el.textContent = txt;
          el.innerHTML = el.textContent.replace(/\n/g, "<br>");
        } else {
          el.textContent = "No field notes yet.";
        }
      } catch (e) {
        // Keep placeholder text if missing/unreachable
        el.textContent = "No field notes yet.";
      }
    }
  }

  onReady(function () {
    const bg = document.getElementById("ctBg") || document.querySelector(".ct-bg");
    const overlay = document.getElementById("ctOverlay");
    const BookEl = document.getElementById("book");
    const FrameEl = document.getElementById("bookFrame");

    if (!bg || !overlay || !BookEl || !FrameEl) return;

    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");

    // ---- Center overlay relative to the contained background image ----
    function positionOverlay() {
      if (!bg.naturalWidth) return; // wait until loaded

      const r = getContainedRect(bg);

      // place overlay at center of the image
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;

      overlay.style.left = cx + "px";
      overlay.style.top = cy + "px";

      // scale book a bit based on available image size
      const targetW = r.width * 0.70; // book fits within 70% of bg width
      const baseBookW = 900;          // must match CSS .book width
      const s = Math.max(0.75, Math.min(1.0, targetW / baseBookW));
      overlay.style.setProperty("--ct-scale", s.toFixed(3));
    }

    const reposition = debounce(positionOverlay, 60);

    if (bg.complete) positionOverlay();
    else bg.addEventListener("load", positionOverlay);

    window.addEventListener("resize", reposition);

    // ---- Hydrate bios from static .txt (does not depend on PageFlip) ----
    hydrateFieldNotes(BookEl).catch(() => {});

    // ---- PageFlip init ----
    const PFClass =
      window.PageFlip ||
      (window.pageFlip && window.pageFlip.PageFlip) ||
      (window.St && window.St.PageFlip) ||
      (window.Page_Flip && window.Page_Flip.PageFlip) ||
      null;

    if (!PFClass) {
      console.warn("PageFlip library not found. Falling back to simple paging.");
      initFallbackPaging(BookEl, prevBtn, nextBtn);
      return;
    }

    let pageFlip;
    try {
      pageFlip = new PFClass(BookEl, {
        // Use the CSS base sizes, but allow stretch to follow scaling
        width: 900,
        height: 650,
        size: "stretch",
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
        autoSize: true,
        display: "double",
      });
    } catch (e) {
      console.error("Failed to initialize PageFlip:", e);
      initFallbackPaging(BookEl, prevBtn, nextBtn);
      return;
    }

    const pages = document.querySelectorAll("#book .page");
    try {
      pageFlip.loadFromHTML(pages);
    } catch (e) {
      console.warn("loadFromHTML failed, falling back", e);
      initFallbackPaging(BookEl, prevBtn, nextBtn);
      return;
    }

    function updateFlip() {
      try { pageFlip.update(); } catch (_) {}
      positionOverlay();
    }

    // Update after images load
    const imgs = BookEl.querySelectorAll("img");
    let pending = imgs.length;

    if (pending) {
      imgs.forEach((img) => {
        if (img.complete) pending--;
        else img.addEventListener("load", () => {
          pending--;
          if (pending <= 0) updateFlip();
        });
      });
      setTimeout(updateFlip, 900);
    } else {
      setTimeout(updateFlip, 150);
    }

    if (prevBtn) prevBtn.addEventListener("click", function (e) {
      e.preventDefault();
      pageFlip.flipPrev();
    });

    if (nextBtn) nextBtn.addEventListener("click", function (e) {
      e.preventDefault();
      pageFlip.flipNext();
    });

    document.addEventListener("keydown", function (e) {
      const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || (e.target && e.target.isContentEditable)) return;

      if (e.key === "ArrowLeft") { e.preventDefault(); pageFlip.flipPrev(); }
      if (e.key === "ArrowRight") { e.preventDefault(); pageFlip.flipNext(); }
    });

    BookEl.addEventListener("click", function (ev) {
      const rect = BookEl.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const edge = rect.width * 0.18;

      if (x <= edge) pageFlip.flipPrev();
      else if (x >= rect.width - edge) pageFlip.flipNext();
    });
  });

  function initFallbackPaging(BookEl, prevBtn, nextBtn) {
    const pages = Array.from(BookEl.querySelectorAll(".page"));
    if (!pages.length) return;

    let idx = 0;
    pages.forEach((p, i) => { p.style.display = (i === idx) ? "block" : "none"; });

    function update() {
      pages.forEach((p, i) => { p.style.display = (i === idx) ? "block" : "none"; });
    }

    if (prevBtn) prevBtn.addEventListener("click", function () {
      idx = Math.max(0, idx - 1);
      update();
    });

    if (nextBtn) nextBtn.addEventListener("click", function () {
      idx = Math.min(pages.length - 1, idx + 1);
      update();
    });
  }
})();