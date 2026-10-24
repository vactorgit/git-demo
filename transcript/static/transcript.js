(() => {
  const $ = (id) => document.getElementById(id);
  const videoId = document.body.dataset.video;
  const ID_RE = /(?:youtube(?:-nocookie)?\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/|live\/|v\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/;

  let data = null;
  let lang = new URLSearchParams(location.search).get("lang") || "";
  let player = null;
  let activeIndex = -1;

  const state = {
    times: true,
    para: false,
    follow: true,
    query: "",
  };

  function parseId(s) {
    s = s.trim();
    if (/^[A-Za-z0-9_-]{11}$/.test(s)) return s;
    const m = s.match(ID_RE);
    return m ? m[1] : null;
  }

  function clock(seconds) {
    const s = Math.floor(seconds);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = String(s % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
  }

  function wordCount(segs) {
    return segs.reduce((n, s) => n + s.text.split(/\s+/).filter(Boolean).length, 0);
  }

  // Group lines into paragraphs of roughly 30 seconds, breaking after sentence ends where possible.
  function paragraphs(segs) {
    const out = [];
    let cur = null;
    for (const s of segs) {
      if (!cur || (s.start - cur.start > 30 && /[.!?]["')\]]?$/.test(cur.text)) || s.start - cur.start > 60) {
        cur = { start: s.start, text: s.text };
        out.push(cur);
      } else {
        cur.text += " " + s.text;
      }
    }
    return out;
  }

  function asText(withTimes) {
    if (!data) return "";
    if (state.para) {
      return paragraphs(data.segments)
        .map((p) => (withTimes ? `[${clock(p.start)}] ` : "") + p.text)
        .join("\n\n");
    }
    if (withTimes) return data.segments.map((s) => `[${clock(s.start)}] ${s.text}`).join("\n");
    return data.segments.map((s) => s.text).join(" ");
  }

  function highlight(el, text, query) {
    if (!query) { el.textContent = text; return; }
    const lower = text.toLowerCase();
    const q = query.toLowerCase();
    let i = 0;
    let at;
    while ((at = lower.indexOf(q, i)) !== -1) {
      el.append(text.slice(i, at));
      const mark = document.createElement("mark");
      mark.textContent = text.slice(at, at + q.length);
      el.append(mark);
      i = at + q.length;
    }
    el.append(text.slice(i));
  }

  function render() {
    const box = $("lines");
    box.textContent = "";
    box.classList.toggle("no-times", !state.times);
    box.classList.toggle("para", state.para);
    activeIndex = -1;

    const items = state.para ? paragraphs(data.segments) : data.segments;
    const q = state.query.trim();
    let shown = 0;
    items.forEach((item, i) => {
      if (q && !item.text.toLowerCase().includes(q.toLowerCase())) return;
      shown++;
      const row = document.createElement("div");
      row.className = "line";
      row.dataset.index = i;
      row.dataset.start = item.start;
      const t = document.createElement("time");
      t.textContent = clock(item.start);
      const p = document.createElement("p");
      highlight(p, item.text, q);
      if (state.para && !state.times) {
        box.append(p);
        p.dataset.start = item.start;
        p.className = "line";
        return;
      }
      row.append(t, p);
      box.append(row);
    });

    const words = wordCount(data.segments).toLocaleString();
    const kind = data.translated ? "translated" : data.is_generated ? "auto-generated" : "creator captions";
    $("status").textContent = q
      ? `${shown} ${shown === 1 ? "match" : "matches"} for “${q}”`
      : `${words} words · ${data.language} (${kind})`;
  }

  function fillLanguages() {
    const sel = $("lang");
    sel.textContent = "";
    const tracks = document.createElement("optgroup");
    tracks.label = "Captions on this video";
    for (const l of data.languages) {
      const o = new Option(l.name + (l.generated ? "" : " ✓"), l.code);
      tracks.append(o);
    }
    sel.append(tracks);
    if (data.translations.length) {
      const tr = document.createElement("optgroup");
      tr.label = "Translate to";
      const have = new Set(data.languages.map((l) => l.code));
      for (const l of data.translations) {
        if (!have.has(l.code)) tr.append(new Option(l.name, l.code));
      }
      sel.append(tr);
    }
    sel.value = data.language_code;
    sel.hidden = data.languages.length + data.translations.length < 2;
  }

  function updateDownloads() {
    const q = lang ? `lang=${encodeURIComponent(lang)}` : "";
    const base = `/download/${videoId}`;
    $("dl-txt").href = `${base}.txt${q ? "?" + q : ""}`;
    $("dl-txt-times").href = `${base}.txt?timestamps=1${q ? "&" + q : ""}`;
    $("dl-srt").href = `${base}.srt${q ? "?" + q : ""}`;
    $("dl-vtt").href = `${base}.vtt${q ? "?" + q : ""}`;
  }

  function remember(title) {
    try {
      const list = JSON.parse(localStorage.getItem("recent") || "[]").filter((r) => r.id !== videoId);
      list.unshift({ id: videoId, title });
      localStorage.setItem("recent", JSON.stringify(list.slice(0, 20)));
    } catch (_) { /* storage unavailable */ }
  }

  async function load() {
    $("status").textContent = "Getting the transcript…";
    try {
      const res = await fetch(`/api/transcript?v=${videoId}${lang ? "&lang=" + encodeURIComponent(lang) : ""}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "Something went wrong.");
      data = body;
    } catch (err) {
      $("lines").textContent = "";
      const p = document.createElement("p");
      p.className = "error";
      p.style.margin = "12px";
      p.textContent = err.message;
      $("lines").append(p);
      $("status").textContent = "No transcript";
      return;
    }

    const info = data.info || {};
    if (info.title) {
      $("vtitle").textContent = info.title;
      document.title = info.title + " · Transcript";
    } else {
      $("vtitle").textContent = "YouTube video " + videoId;
    }
    $("vauthor").textContent = info.author || "";
    remember(info.title);
    fillLanguages();
    updateDownloads();
    render();
  }

  // ---- Video player sync ----
  window.onYouTubeIframeAPIReady = () => {
    player = new YT.Player("player", {
      videoId,
      playerVars: { rel: 0, modestbranding: 1, playsinline: 1 },
    });
    setInterval(tick, 300);
  };

  function tick() {
    if (!data || !player || typeof player.getCurrentTime !== "function") return;
    const t = player.getCurrentTime();
    const rows = $("lines").querySelectorAll(".line");
    let idx = -1;
    for (let i = 0; i < rows.length; i++) {
      if (Number(rows[i].dataset.start) <= t + 0.25) idx = i; else break;
    }
    if (idx === activeIndex) return;
    if (activeIndex >= 0 && rows[activeIndex]) rows[activeIndex].classList.remove("active");
    activeIndex = idx;
    const row = rows[idx];
    if (!row) return;
    row.classList.add("active");
    const playing = player.getPlayerState && player.getPlayerState() === 1;
    if (state.follow && playing && !state.query) {
      const box = $("lines");
      const top = row.offsetTop - box.offsetTop - box.clientHeight / 3;
      box.scrollTo({ top, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    }
  }

  $("lines").addEventListener("click", (e) => {
    const row = e.target.closest(".line");
    if (!row || !player || typeof player.seekTo !== "function") return;
    player.seekTo(Number(row.dataset.start), true);
    player.playVideo();
  });

  // ---- Toolbar ----
  function toggle(id, key) {
    $(id).addEventListener("click", () => {
      state[key] = !state[key];
      $(id).setAttribute("aria-pressed", String(state[key]));
      if (data && key !== "follow") render();
    });
  }
  toggle("times", "times");
  toggle("para", "para");
  toggle("follow", "follow");

  $("search").addEventListener("input", (e) => { state.query = e.target.value; if (data) render(); });

  $("lang").addEventListener("change", (e) => {
    lang = e.target.value;
    const url = new URL(location.href);
    url.searchParams.set("lang", lang);
    history.replaceState(null, "", url);
    $("summary").textContent = "Get the main points of this video in a few seconds.";
    load();
  });

  $("copy").addEventListener("click", async () => {
    const btn = $("copy");
    try {
      await navigator.clipboard.writeText(asText(state.times));
      btn.textContent = "Copied";
    } catch (_) {
      const range = document.createRange();
      range.selectNodeContents($("lines"));
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
      btn.textContent = "Selected. Press Ctrl+C";
    }
    setTimeout(() => (btn.textContent = "Copy"), 2000);
  });

  $("dl").addEventListener("click", (e) => {
    e.stopPropagation();
    const menu = $("dl-menu");
    menu.hidden = !menu.hidden;
    $("dl").setAttribute("aria-expanded", String(!menu.hidden));
  });
  document.addEventListener("click", () => { $("dl-menu").hidden = true; $("dl").setAttribute("aria-expanded", "false"); });

  $("summarize").addEventListener("click", async () => {
    const btn = $("summarize");
    btn.disabled = true;
    $("summary").textContent = "Summarizing…";
    try {
      const res = await fetch("/api/summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ v: videoId, lang }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "Something went wrong.");
      $("summary").textContent = body.summary;
      btn.textContent = "Redo";
    } catch (err) {
      $("summary").textContent = err.message;
    } finally {
      btn.disabled = false;
    }
  });

  $("topform").addEventListener("submit", (e) => {
    e.preventDefault();
    const id = parseId($("topurl").value);
    if (id) location.href = "/transcript?v=" + id;
  });
  $("topurl").addEventListener("paste", () => setTimeout(() => {
    if (parseId($("topurl").value)) $("topform").requestSubmit();
  }, 0));

  updateDownloads();
  load();
})();
