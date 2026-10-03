"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options = {}) {
  const opts = { ...options };
  if (opts.body && typeof opts.body !== "string" && !(opts.body instanceof Blob)) {
    opts.body = JSON.stringify(opts.body);
    opts.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) { /* pas de JSON */ }
    throw new Error(detail);
  }
  return res.json();
}

function fmt(t) {
  t = Math.max(0, Math.round(t || 0));
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
  return (h ? `${h}:${String(m).padStart(2, "0")}` : `${m}`) + `:${String(s).padStart(2, "0")}`;
}

function toast(msg, isError = false) {
  const el = $("#banner");
  el.textContent = msg;
  el.style.background = isError ? "#3a1616" : "";
  el.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add("hidden"), 6000);
}

/* ------------------------------------------------------------------ onglets */
$("#btn-quit").addEventListener("click", async () => {
  const running = state.projects.some((p) => p.busy) || state.refsBusy;
  const msg = running
    ? "Un traitement est en cours : il sera interrompu (tu pourras le reprendre avec « Continuer »). Quitter KrokCut ?"
    : "Quitter KrokCut ?";
  if (!confirm(msg)) return;
  try { await api("/api/quit", { method: "POST" }); } catch (_) { /* le serveur s'arrête */ }
  document.body.innerHTML = '<div class="card" style="max-width:520px;margin:15vh auto;text-align:center"><h2>KrokCut est fermé 👋</h2><p class="muted">Pour le rouvrir : double-clic sur l\'app KrokCut.</p></div>';
});

$$(".tab[data-view]").forEach((tab) =>
  tab.addEventListener("click", () => {
    $$(".tab[data-view]").forEach((t) => t.classList.toggle("active", t === tab));
    $$(".view").forEach((v) => v.classList.toggle("hidden", v.id !== `view-${tab.dataset.view}`));
    if (tab.dataset.view === "library") loadLibrary();
    if (tab.dataset.view === "settings") loadSettings();
    if (tab.dataset.view === "references") loadReferences();
  })
);

/* ----------------------------------------------------------------- épisodes */
const state = { projects: [], current: null, review: null, files: { a: [], b: [] }, pollTimer: null };

async function loadProjects() {
  state.projects = await api("/api/projects");
  const list = $("#project-list");
  list.innerHTML = state.projects
    .map((p) => {
      const done = p.steps.filter((s) => s.status === "done").length;
      const status = p.busy ? "⏳ en cours" : p.last_error ? "⚠️ erreur" : `${done}/${p.steps.length} étapes`;
      return `<li data-id="${esc(p.id)}" class="${state.current === p.id ? "active" : ""}">${esc(p.name)}<small>${esc(status)}</small></li>`;
    })
    .join("");
  $$("li", list).forEach((li) => li.addEventListener("click", () => openProject(li.dataset.id)));
  $("#empty").classList.toggle("hidden", state.current !== null || !$("#new-project").classList.contains("hidden"));
}

$("#btn-new").addEventListener("click", () => {
  state.current = null;
  state.files = { a: [], b: [] };
  renderFiles();
  $("#new-project").classList.remove("hidden");
  $("#project-detail").classList.add("hidden");
  $("#empty").classList.add("hidden");
  api("/api/style").then((s) => {
    $("#np-min").value = s.target_min_minutes;
    $("#np-max").value = s.target_max_minutes;
  });
});
$("#np-cancel").addEventListener("click", () => {
  $("#new-project").classList.add("hidden");
  loadProjects();
});

function renderFiles() {
  for (const pov of ["a", "b"]) {
    $(`#files-${pov}`).innerHTML = state.files[pov]
      .map(
        (f, i) =>
          `<li><span>${esc(f.path || f.name)}</span>${
            f.progress !== undefined && f.progress < 1 ? `<span class="progress">${Math.round(f.progress * 100)} %</span>` : ""
          }<button class="ghost small" data-remove="${pov}:${i}">✕</button></li>`
      )
      .join("");
  }
  $$("[data-remove]").forEach((b) =>
    b.addEventListener("click", () => {
      const [pov, i] = b.dataset.remove.split(":");
      state.files[pov].splice(Number(i), 1);
      renderFiles();
    })
  );
}

/** Envoie un fichier au serveur en flux ; renvoie le chemin où il a été enregistré. */
function putFile(file, folder, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `/api/upload/${encodeURIComponent(file.name)}?folder=${folder}`);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText).path);
      else reject(new Error(xhr.responseText));
    };
    xhr.onerror = () => reject(new Error("Échec de l'envoi"));
    xhr.send(file);
  });
}

async function uploadFile(file, pov) {
  const entry = { name: file.name, progress: 0 };
  state.files[pov].push(entry);
  renderFiles();
  entry.path = await putFile(file, "rush", (p) => { entry.progress = p; renderFiles(); });
  entry.progress = 1;
  renderFiles();
}

$$(".dropzone[data-pov]").forEach((zone) => {
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", async (e) => {
    e.preventDefault();
    zone.classList.remove("over");
    for (const file of e.dataTransfer.files) {
      try { await uploadFile(file, zone.dataset.pov); } catch (err) { toast(`Envoi impossible : ${err.message}`, true); }
    }
  });
});

$("#np-start").addEventListener("click", async () => {
  const pending = [...state.files.a, ...state.files.b].some((f) => !f.path);
  if (pending) return toast("Attends la fin de la copie des fichiers.", true);
  if (!state.files.a.length || !state.files.b.length) return toast("Ajoute un fichier pour chaque POV.", true);
  const body = {
    name: $("#np-name").value.trim() || "Épisode sans titre",
    pov_a: state.files.a.map((f) => f.path),
    pov_b: state.files.b.map((f) => f.path),
    name_a: $("#np-name-a").value.trim() || "Krok",
    name_b: $("#np-name-b").value.trim() || "Mil",
    target_min: Number($("#np-min").value) || null,
    target_max: Number($("#np-max").value) || null,
    pause_after_story: $("#np-pause").checked,
  };
  try {
    const p = await api("/api/projects", { method: "POST", body });
    $("#new-project").classList.add("hidden");
    openProject(p.id);
  } catch (err) {
    toast(err.message, true);
  }
});

/* ------------------------------------------------------------- explorateur */
let onBrowsePick = null;
function openBrowser(onPick) {
  onBrowsePick = onPick;
  $("#browser").showModal();
  let last = "";
  try { last = localStorage.getItem("krokcut-last-dir") || ""; } catch (_) { /* stockage indisponible */ }
  browseTo(last);
}
async function browseTo(path) {
  try {
    const data = await api(`/api/browse?path=${encodeURIComponent(path || "")}`);
    $("#br-path").value = data.path;
    const rows = [];
    if (data.parent) rows.push(`<li data-dir="${esc(data.parent)}">⬆️ ..</li>`);
    const sep = data.path.includes("\\") ? "\\" : "/";
    for (const d of data.dirs) {
      const full = data.path ? data.path.replace(/[\\/]$/, "") + sep + d : d;
      rows.push(`<li data-dir="${esc(full)}">📁 ${esc(d)}</li>`);
    }
    for (const f of data.files) {
      const full = data.path.replace(/[\\/]$/, "") + sep + f.name;
      rows.push(`<li class="file"><input type="checkbox" value="${esc(full)}"> 🎞️ ${esc(f.name)}<small>${(f.size / 1e9).toFixed(2)} Go</small></li>`);
    }
    $("#br-list").innerHTML = rows.join("") || "<li>Aucune vidéo ici</li>";
    $$("#br-list [data-dir]").forEach((li) => li.addEventListener("click", () => browseTo(li.dataset.dir)));
    $$("#br-list li.file").forEach((li) =>
      li.addEventListener("click", (e) => {
        if (e.target.tagName !== "INPUT") $("input", li).checked = !$("input", li).checked;
      })
    );
  } catch (err) {
    toast(err.message, true);
  }
}
$$("[data-browse]").forEach((b) =>
  b.addEventListener("click", () =>
    openBrowser((paths) => {
      paths.forEach((p) => state.files[b.dataset.browse].push({ name: p, path: p }));
      renderFiles();
    })
  )
);
$("#br-go").addEventListener("click", () => browseTo($("#br-path").value));
$("#br-add").addEventListener("click", () => {
  const picked = $$("#br-list input:checked").map((i) => i.value);
  try { localStorage.setItem("krokcut-last-dir", $("#br-path").value); } catch (_) { /* stockage indisponible */ }
  $("#browser").close();
  if (onBrowsePick && picked.length) onBrowsePick(picked);
});

/* ---------------------------------------------------------------- détail */
const ICONS = { pending: "○", running: "⏳", done: "✅", error: "❌", skipped: "⏭️" };

async function openProject(id) {
  state.current = id;
  state.review = null;
  $("#new-project").classList.add("hidden");
  $("#empty").classList.add("hidden");
  $("#project-detail").classList.remove("hidden");
  await refreshProject(true);
  loadProjects();
}

async function refreshProject(full = false) {
  if (!state.current) return;
  let p;
  try {
    p = await api(`/api/projects/${state.current}`);
  } catch (err) {
    return toast(err.message, true);
  }
  $("#pd-name").textContent = p.name;
  $("#pd-sources").textContent = `POV A : ${p.sources.A.name} (${fmt(p.sources.A.duration)}) · POV B : ${p.sources.B.name} (${fmt(p.sources.B.duration)})`;
  $("#pd-steps").innerHTML = p.steps
    .map(
      (s) => `<li class="${s.status}"><span class="icon">${ICONS[s.status] || "○"}</span><div>
        <div class="label">${esc(s.label)}</div>
        ${s.message ? `<div class="msg">${esc(s.message)}</div>` : ""}
        ${s.status === "running" ? `<div class="bar"><i style="width:${Math.round(s.progress * 100)}%"></i></div>` : ""}
      </div></li>`
    )
    .join("");
  const busy = p.busy;
  $("#pd-busy").classList.toggle("hidden", !busy);
  $("#pd-busy").textContent = busy === "queued" ? "en file d'attente" : "traitement en cours";
  $("#pd-cancel").classList.toggle("hidden", !busy);
  const allDone = p.steps.every((s) => s.status === "done");
  $("#pd-run").classList.toggle("hidden", !!busy || allDone);
  $("#pd-run").textContent = p.steps.some((s) => s.status === "error") ? "Réessayer" : "Continuer";
  $("#pd-error").classList.toggle("hidden", !p.last_error);
  $("#pd-error").textContent = p.last_error || "";
  $("#pd-log").textContent = (p.log || []).join("\n");
  $("#pd-claude").checked = p.use_claude;
  if (full) {
    $("#pd-from").innerHTML = p.steps.map((s) => `<option value="${s.id}">${esc(s.label)}</option>`).join("");
    $("#pd-offset").value = p.manual_offset ?? "";
  }

  // Résultats
  const outputs = p.outputs || [];
  const video = outputs.includes("montage_final.mp4") ? "montage_final.mp4" : outputs.includes("montage_preview.mp4") ? "montage_preview.mp4" : null;
  $("#pd-result").classList.toggle("hidden", !outputs.length);
  if (video) {
    const src = `/api/projects/${p.id}/out/${video}?v=${encodeURIComponent(p.steps.find((s) => s.id === "render").finished || "")}`;
    if ($("#pd-video").dataset.src !== src) {
      $("#pd-video").dataset.src = src;
      $("#pd-video").src = src;
    }
  }
  const labels = {
    "montage_preview.mp4": "🎞️ Aperçu MP4",
    "montage_final.mp4": "🎬 Vidéo finale MP4",
    "timeline_premiere_davinci.xml": "🧩 Timeline Premiere / DaVinci (XML)",
    "sous_titres.srt": "💬 Sous-titres SRT",
    "chapitres_youtube.txt": "📑 Chapitres YouTube",
    "recap.md": "📝 Récap, titres et miniatures",
  };
  $("#pd-downloads").innerHTML = outputs
    .map((f) => `<a href="/api/projects/${p.id}/out/${encodeURIComponent(f)}" download>${labels[f] || esc(f)}</a>`)
    .join("");
  $("#pd-final").disabled = !!busy;
  $("#pd-preview").disabled = !!busy;

  // Revue des moments dès que l'histoire existe
  const storyDone = p.steps.find((s) => s.id === "story").status === "done";
  $("#pd-review").classList.toggle("hidden", !storyDone);
  if (storyDone && (!state.review || full || state.reviewStamp !== p.steps.find((s) => s.id === "story").finished)) {
    state.reviewStamp = p.steps.find((s) => s.id === "story").finished;
    loadReview();
  }
  $("#rv-save").disabled = !!busy;

  clearTimeout(state.pollTimer);
  if (busy) state.pollTimer = setTimeout(() => refreshProject(), 1500);
  else if (state.wasBusy) loadProjects();
  state.wasBusy = !!busy;
}

async function runProject(body) {
  try {
    await api(`/api/projects/${state.current}/run`, { method: "POST", body });
    refreshProject();
    loadProjects();
  } catch (err) {
    toast(err.message, true);
  }
}

$("#pd-run").addEventListener("click", () => runProject({ use_claude: $("#pd-claude").checked }));
$("#pd-cancel").addEventListener("click", async () => {
  await api(`/api/projects/${state.current}/cancel`, { method: "POST" });
  refreshProject();
});
$("#pd-rerun").addEventListener("click", () => runProject({ from_step: $("#pd-from").value, use_claude: $("#pd-claude").checked }));
$("#pd-offset-apply").addEventListener("click", () => {
  const v = $("#pd-offset").value.trim();
  runProject(v === "" ? { from_step: "sync", clear_offset: true } : { from_step: "sync", manual_offset: Number(v) });
});
$("#pd-final").addEventListener("click", () => runProject({ from_step: "render", quality: "final" }));
$("#pd-preview").addEventListener("click", () => runProject({ from_step: "render", quality: "preview" }));

/* ------------------------------------------------------------ revue moments */
async function loadReview() {
  const data = await api(`/api/projects/${state.current}/review`);
  const inStory = new Map((data.story?.sequence || []).map((s, i) => [s.moment, { ...s, order: i }]));
  const moments = data.moments.map((m) => ({ ...m, picked: inStory.has(m.id), item: inStory.get(m.id) }));
  // ordre : moments retenus dans l'ordre de l'histoire, puis les autres chronologiquement
  const picked = moments.filter((m) => m.picked).sort((a, b) => a.item.order - b.item.order);
  const others = moments.filter((m) => !m.picked);
  state.review = { ...data, list: [...picked, ...others] };
  renderReview();
}

function reviewTotal() {
  const r = state.review;
  let total = r.list.filter((m) => m.picked).reduce((acc, m) => acc + (m.item?.est_duration ?? m.est_duration), 0);
  if (r.story?.cold_open) total += r.story.cold_open.est_duration || 0;
  return total;
}

function renderReview() {
  const r = state.review;
  const onlyPicked = $("#rv-only").checked;
  const total = reviewTotal();
  const lo = r.style.target_min_minutes * 60, hi = r.style.target_max_minutes * 60;
  $("#rv-total").textContent = fmt(total);
  $(".total").classList.toggle("over", total > hi || total < lo);
  $("#rv-target").textContent = `cible ${fmt(lo)} – ${fmt(hi)}`;
  const co = r.story?.cold_open;
  $("#rv-cold").innerHTML = co
    ? `🎣 <b>Teaser d'ouverture</b> : ${esc(co.title)} (${Math.round(co.est_duration)} s) <button class="ghost small" id="rv-cold-off">Retirer</button>`
    : "🎣 Pas de teaser d'ouverture.";
  if (co) $("#rv-cold-off").addEventListener("click", () => { r.story.cold_open = null; r.coldChanged = true; renderReview(); });

  $("#rv-list").innerHTML = r.list
    .map((m, i) => {
      if (onlyPicked && !m.picked) return "";
      const dur = m.item?.est_duration ?? m.est_duration;
      const mid = (m.start + m.end) / 2;
      return `<li class="moment ${m.picked ? "on" : "off"}" data-i="${i}">
        <input type="checkbox" ${m.picked ? "checked" : ""} data-pick="${i}">
        <div class="thumbs">
          <img loading="lazy" src="/api/projects/${state.current}/thumb?t=${mid.toFixed(1)}&pov=A" alt="">
          <img loading="lazy" src="/api/projects/${state.current}/thumb?t=${mid.toFixed(1)}&pov=B" alt="">
        </div>
        <div>
          <div class="title">${esc(m.title)}</div>
          <div class="meta"><span class="badge">${esc(m.kind)}</span>${fmt(m.start)} → ${fmt(m.end)} · ${Math.round(dur)} s · humour ${m.humor}/10 · énergie ${m.energy}/10 · histoire ${m.story}/10</div>
          <div class="quote">« ${esc(m.key_quote)} »</div>
          ${m.why ? `<div class="meta">${esc(m.why)}</div>` : ""}
          <button class="ghost small" data-lines="${i}">Voir la transcription</button>
        </div>
        <div class="order">
          <button class="ghost small" data-up="${i}" title="Monter">▲</button>
          <button class="ghost small" data-down="${i}" title="Descendre">▼</button>
        </div>
        <div class="lines hidden" id="lines-${i}"></div>
      </li>`;
    })
    .join("");

  $$("[data-pick]").forEach((cb) =>
    cb.addEventListener("change", () => {
      r.list[Number(cb.dataset.pick)].picked = cb.checked;
      renderReview();
    })
  );
  $$("[data-up]").forEach((b) => b.addEventListener("click", () => move(Number(b.dataset.up), -1)));
  $$("[data-down]").forEach((b) => b.addEventListener("click", () => move(Number(b.dataset.down), 1)));
  $$("[data-lines]").forEach((b) =>
    b.addEventListener("click", async () => {
      const i = Number(b.dataset.lines);
      const box = $(`#lines-${i}`);
      if (!box.classList.contains("hidden")) return box.classList.add("hidden");
      const m = r.list[i];
      const lines = await api(`/api/projects/${state.current}/lines?start=${m.start_line}&end=${m.end_line}`);
      box.textContent = lines.map((l) => `#${l.id} [${fmt(l.start)}] ${l.kind === "event" ? "" : (r.names[l.speaker] || "?") + " : "}${l.text}`).join("\n");
      box.classList.remove("hidden");
    })
  );
}

function move(i, delta) {
  const list = state.review.list;
  const j = i + delta;
  if (j < 0 || j >= list.length) return;
  [list[i], list[j]] = [list[j], list[i]];
  renderReview();
}

$("#rv-only").addEventListener("change", renderReview);
$("#rv-save").addEventListener("click", async () => {
  const r = state.review;
  const sequence = r.list
    .filter((m) => m.picked)
    .map((m) => ({
      moment: m.id,
      title: m.title,
      start_line: m.item?.start_line ?? m.start_line,
      end_line: m.item?.end_line ?? m.end_line,
      chapter: m.item?.chapter ?? "",
      transition: m.item?.transition ?? "cut",
    }));
  if (!sequence.length) return toast("Choisis au moins un moment.", true);
  const body = { sequence };
  if (r.coldChanged) body.cold_open = r.story.cold_open || { moment: "" };
  try {
    const res = await api(`/api/projects/${state.current}/story`, { method: "POST", body });
    toast(`Sélection enregistrée (${fmt(res.total_estimate)}). Montage relancé.`);
    refreshProject();
  } catch (err) {
    toast(err.message, true);
  }
});

/* ------------------------------------------------------------ bibliothèque */
let libAssets = [];
async function loadLibrary() {
  const data = await api("/api/library");
  $("#lib-dir").value = data.dir || "";
  libAssets = data.assets;
  renderLibrary(data.stats);
}

function renderLibrary(stats) {
  if (stats) {
    const names = { sfx: "bruitages", music: "musiques", character: "animations de persos", image: "images", video: "clips" };
    $("#lib-stats").textContent = Object.entries(stats).map(([k, v]) => `${v} ${names[k] || k}`).join(" · ") || "Bibliothèque vide.";
  }
  const q = $("#lib-filter").value.toLowerCase();
  const kind = $("#lib-kind").value;
  const rows = libAssets.filter(
    (a) => (!kind || a.kind === kind) && (!q || [a.id, a.name, a.character, ...a.tags].join(" ").toLowerCase().includes(q))
  );
  $("#lib-rows").innerHTML = rows
    .slice(0, 400)
    .map((a) => {
      const url = `/api/library/file?id=${encodeURIComponent(a.id)}`;
      let preview = "";
      if (a.kind === "sfx" || a.kind === "music") preview = `<audio controls preload="none" src="${url}"></audio>`;
      else if (/\.(png|gif|jpe?g|webp)$/i.test(a.path)) preview = `<img loading="lazy" src="${url}" alt="">`;
      else preview = `<video muted preload="none" src="${url}" onmouseover="this.play()" onmouseout="this.pause()"></video>`;
      return `<tr>
        <td>${esc(a.kind)}</td>
        <td class="id"><b>${esc(a.name)}</b><br><small class="muted">${esc(a.id)}</small></td>
        <td>${esc(a.character || "")}</td>
        <td><input type="text" value="${esc(a.tags.join(", "))}" data-tags="${esc(a.id)}"></td>
        <td>${a.duration ? a.duration.toFixed(1) + " s" : ""}</td>
        <td><input type="checkbox" ${a.enabled ? "checked" : ""} data-enabled="${esc(a.id)}"></td>
        <td>${preview}</td>
      </tr>`;
    })
    .join("");
  $$("[data-tags]").forEach((input) =>
    input.addEventListener("change", () =>
      updateAsset(input.dataset.tags, { tags: input.value.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean) })
    )
  );
  $$("[data-enabled]").forEach((cb) => cb.addEventListener("change", () => updateAsset(cb.dataset.enabled, { enabled: cb.checked })));
}

async function updateAsset(id, changes) {
  try {
    const updated = await api("/api/library/update", { method: "POST", body: { id, changes } });
    const i = libAssets.findIndex((a) => a.id === id);
    if (i >= 0) libAssets[i] = updated;
  } catch (err) {
    toast(err.message, true);
  }
}

$("#lib-scan").addEventListener("click", async () => {
  $("#lib-scan").disabled = true;
  $("#lib-stats").textContent = "Scan en cours…";
  try {
    const data = await api("/api/library/scan", { method: "POST", body: { dir: $("#lib-dir").value } });
    libAssets = data.assets;
    renderLibrary(data.stats);
  } catch (err) {
    toast(err.message, true);
  } finally {
    $("#lib-scan").disabled = false;
  }
});
$("#lib-filter").addEventListener("input", () => renderLibrary());
$("#lib-kind").addEventListener("change", () => renderLibrary());

/* ---------------------------------------------------------------- réglages */
const STYLE_FIELDS = [
  ["target_min_minutes", "Durée min (min)", "number"],
  ["target_max_minutes", "Durée max (min)", "number"],
  ["cold_open", "Teaser d'ouverture", "bool"],
  ["layout", "Réalisation", ["switch", "pip", "split"]],
  ["audio_mode", "Son", ["follow", "mix", "A", "B"]],
  ["min_shot", "Plan minimum (s)", "number"],
  ["max_silence", "Blanc max conservé (s)", "number"],
  ["zooms_per_minute", "Zooms / minute", "number"],
  ["punch_scale", "Force du zoom", "number"],
  ["sfx_per_minute", "Bruitages / minute", "number"],
  ["sfx_volume_db", "Volume bruitages (dB)", "number"],
  ["characters_per_minute", "Persos / minute", "number"],
  ["character_scale", "Taille des persos (0–1)", "number"],
  ["texts_per_minute", "Textes / minute", "number"],
  ["voice_polish", "Traitement des voix", "bool"],
  ["denoise", "Débruitage", "bool"],
  ["music", "Musique de fond", "bool"],
  ["music_volume_db", "Volume musique (dB)", "number"],
];
const OPTION_LABELS = {
  switch: "Un POV à la fois", pip: "POV + incrustation de l'autre", split: "Écran partagé",
  follow: "Suit le POV affiché", mix: "Mix des deux POV", A: "Toujours POV A", B: "Toujours POV B",
};

async function loadSettings() {
  const cfg = await api("/api/config");
  $("#cfg-key").value = "";
  $("#cfg-key-hint").textContent = cfg.claude ? `Clé enregistrée : ${cfg.api_key_hint || "via variable d'environnement"} · modèle ${cfg.model}` : "Aucune clé : KrokCut fonctionnera en mode hors ligne (bien moins malin).";
  $("#cfg-whisper").value = cfg.whisper_model;
  $("#cfg-device").value = cfg.whisper_device;
  $("#cfg-codec").value = cfg.video_codec;
  $("#cfg-font").value = cfg.font_file;
  $("#cfg-workspace").textContent = `Espace de travail : ${cfg.workspace}`;

  const style = await api("/api/style");
  $("#style-form").innerHTML = STYLE_FIELDS.map(([key, label, type]) => {
    if (Array.isArray(type))
      return `<label>${label}<select data-style="${key}">${type.map((o) => `<option value="${o}" ${style[key] === o ? "selected" : ""}>${OPTION_LABELS[o] || o}</option>`).join("")}</select></label>`;
    if (type === "bool") return `<label class="check"><input type="checkbox" data-style="${key}" ${style[key] ? "checked" : ""}> ${label}</label>`;
    return `<label>${label}<input type="number" step="any" data-style="${key}" value="${style[key]}"></label>`;
  }).join("");
  $("#style-notes").value = style.notes || "";
  $("#bible").value = (await api("/api/chaine")).text;
}

$("#cfg-save").addEventListener("click", async () => {
  const body = {
    whisper_model: $("#cfg-whisper").value,
    whisper_device: $("#cfg-device").value,
    video_codec: $("#cfg-codec").value,
    font_file: $("#cfg-font").value,
  };
  if ($("#cfg-key").value.trim()) body.anthropic_api_key = $("#cfg-key").value.trim();
  await api("/api/config", { method: "POST", body });
  toast("Réglages enregistrés.");
  loadSettings();
  checkClaude();
});
$("#style-save").addEventListener("click", async () => {
  const body = { notes: $("#style-notes").value };
  $$("[data-style]").forEach((el) => {
    body[el.dataset.style] = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
  });
  await api("/api/style", { method: "POST", body });
  toast("Style enregistré (s'applique aux nouveaux épisodes).");
});
$("#bible-save").addEventListener("click", async () => {
  await api("/api/chaine", { method: "POST", body: { text: $("#bible").value } });
  toast("Bible de la chaîne enregistrée.");
});

async function checkClaude() {
  const cfg = await api("/api/config");
  $("#empty-claude").textContent = cfg.claude
    ? `Claude est connecté (${cfg.model}).`
    : "⚠️ Aucune clé Claude configurée : ajoute-la dans Réglages, sinon le dérush se fera en mode hors ligne (pics sonores uniquement).";
}

async function checkReferences() {
  try {
    const data = await api("/api/references");
    const n = data.references.length;
    $("#empty-refs").textContent = n
      ? `🎓 ${n} vidéo${n > 1 ? "s" : ""} déjà montée${n > 1 ? "s" : ""} prise${n > 1 ? "s" : ""} en compte pour comprendre votre style.`
      : "🎓 Astuce : dépose 3 à 5 de vos vidéos déjà montées dans l'onglet « Mes vidéos » pour que KrokCut apprenne votre style.";
  } catch (_) { /* pas grave */ }
}

checkClaude();
checkReferences();
loadProjects();

/* ------------------------------------------------------------- mes vidéos */
const REF_ICONS = { pending: "○", running: "⏳", done: "✅", error: "❌", skipped: "⏭️" };
const SUGGEST_LABELS = {
  target_min_minutes: "Durée min (min)", target_max_minutes: "Durée max (min)", sfx_per_minute: "Bruitages / minute",
  zooms_per_minute: "Zooms / minute", texts_per_minute: "Textes / minute", characters_per_minute: "Persos / minute",
  music: "Musique de fond", cold_open: "Teaser d'ouverture",
};
state.refOpen = new Set();
state.refUploads = [];

/** Markdown minimal (titres, listes, gras) — le texte est échappé avant. */
function miniMarkdown(md) {
  const out = [];
  let inList = false;
  for (const raw of String(md || "").split("\n")) {
    let line = esc(raw.trim()).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    const item = /^[-*] (.*)/.exec(line);
    if (item) {
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push(`<li>${item[1]}</li>`);
      continue;
    }
    if (inList) { out.push("</ul>"); inList = false; }
    const heading = /^(#{1,4}) (.*)/.exec(line);
    if (heading) out.push(`<h${Math.min(4, heading[1].length + 2)}>${heading[2]}</h${Math.min(4, heading[1].length + 2)}>`);
    else if (line) out.push(`<p>${line}</p>`);
  }
  if (inList) out.push("</ul>");
  return out.join("");
}

function refMetrics(m) {
  const parts = [];
  if (m.duration_min) parts.push(`${m.duration_min} min`);
  if (m.cuts_per_min !== undefined) parts.push(`${m.cuts_per_min} plans/min`);
  if (m.median_shot) parts.push(`plan médian ${m.median_shot} s`);
  if (m.sfx_checked) parts.push(`${m.sfx_hits || 0} bruitages reconnus`);
  if (m.speech_ratio !== undefined) parts.push(`parole ${Math.round(m.speech_ratio * 100)} %`);
  return parts.join(" · ");
}

async function loadReferences() {
  let data;
  try { data = await api("/api/references"); } catch (err) { return toast(err.message, true); }
  state.refsBusy = data.references.some((r) => r.busy) || data.guide_busy;
  renderReferences(data);
  clearTimeout(state.refTimer);
  if (state.refsBusy && !$("#view-references").classList.contains("hidden")) state.refTimer = setTimeout(loadReferences, 2000);
}

function renderReferences(data) {
  // vidéos
  $("#ref-list").innerHTML = data.references
    .slice()
    .reverse()
    .map((r) => {
      const running = r.steps.find((s) => s.status === "running");
      const failed = r.steps.find((s) => s.status === "error");
      const done = r.steps.every((s) => s.status === "done");
      const halted = !running && !failed && !r.busy ? r.steps.find((s) => s.status === "pending" && s.message) : null;
      const status = r.busy === "queued" ? "en file d'attente" : running ? running.label : failed ? "erreur" : done ? "analysée" : "en attente";
      const thumb = r.has_thumb
        ? `<img class="ref-thumb" loading="lazy" src="/api/references/${encodeURIComponent(r.id)}/thumb" alt="">`
        : `<div class="ref-thumb empty">🎞️</div>`;
      return `<li class="ref" data-id="${esc(r.id)}">
        ${thumb}
        <div class="ref-body">
          <div class="row space"><b>${esc(r.name)}</b><span class="pill ${failed ? "bad" : ""}">${esc(status)}</span></div>
          <div class="meta">${esc(refMetrics(r.metrics)) || "&nbsp;"}</div>
          ${running ? `<div class="msg">${esc(running.message || "")}</div><div class="bar"><i style="width:${Math.round(running.progress * 100)}%"></i></div>` : ""}
          ${failed ? `<div class="error">${esc(failed.label)} : ${esc(failed.message)}</div>` : ""}
          ${halted ? `<div class="msg">⏸ ${esc(halted.label)} : ${esc(halted.message)}</div>` : ""}
          ${r.steps.filter((s) => s.status === "done" && s.message).map((s) => `<div class="msg">${REF_ICONS.done} ${esc(s.label)} : ${esc(s.message)}</div>`).join("")}
          <div class="row wrap">
            ${r.analysis_source ? `<button class="ghost small" data-ref-details="${esc(r.id)}">${state.refOpen.has(r.id) ? "Masquer l'analyse" : "Voir l'analyse"}</button>` : ""}
            ${r.busy ? `<button class="ghost small" data-ref-cancel="${esc(r.id)}">Annuler</button>` : (done
              ? `<button class="ghost small" data-ref-rerun="${esc(r.id)}" title="Refait la recherche des bruitages et l'analyse du style">Réanalyser</button>`
              : `<button class="ghost small" data-ref-rerun="${esc(r.id)}">Reprendre l'analyse</button>`)}
            <button class="ghost small" data-ref-delete="${esc(r.id)}">Retirer</button>
          </div>
          <div class="ref-details ${state.refOpen.has(r.id) ? "" : "hidden"}" id="ref-details-${esc(r.id)}"></div>
        </div>
      </li>`;
    })
    .join("") || "";
  state.refOpen.forEach((id) => { if (data.references.some((r) => r.id === id)) loadRefDetails(id); });

  $$("[data-ref-details]").forEach((b) => b.addEventListener("click", () => {
    const id = b.dataset.refDetails;
    if (state.refOpen.has(id)) state.refOpen.delete(id); else state.refOpen.add(id);
    renderReferences(data);
  }));
  $$("[data-ref-rerun]").forEach((b) => b.addEventListener("click", async () => {
    try { await api(`/api/references/${encodeURIComponent(b.dataset.refRerun)}/run`, { method: "POST", body: {} }); loadReferences(); }
    catch (err) { toast(err.message, true); }
  }));
  $$("[data-ref-cancel]").forEach((b) => b.addEventListener("click", async () => {
    await api(`/api/references/${encodeURIComponent(b.dataset.refCancel)}/cancel`, { method: "POST" });
    loadReferences();
  }));
  $$("[data-ref-delete]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("Retirer cette vidéo ? Le guide de style sera recalculé sans elle.")) return;
    try { await api(`/api/references/${encodeURIComponent(b.dataset.refDelete)}`, { method: "DELETE" }); loadReferences(); }
    catch (err) { toast(err.message, true); }
  }));

  // guide
  const g = data.guide;
  $("#guide-card").classList.toggle("hidden", !g && !data.guide_busy && !data.guide_error);
  $("#guide-error").classList.toggle("hidden", !data.guide_error);
  $("#guide-error").textContent = data.guide_error ? `La mise à jour du guide a échoué : ${data.guide_error}` : "";
  const n = g ? g.sources.length : 0;
  $("#guide-meta").textContent = data.guide_busy
    ? "Mise à jour du guide en cours…"
    : g
      ? `Tiré de ${n} vidéo${n > 1 ? "s" : ""} · ${g.source === "claude" ? "rédigé par Claude" : "mesures seules (ajoute une clé Claude pour un vrai guide)"} · mis à jour le ${new Date(g.updated).toLocaleString("fr-FR")}` +
        ((g.ignored || []).length ? ` · ignorée${g.ignored.length > 1 ? "s" : ""} car trop longue${g.ignored.length > 1 ? "s" : ""} (plus d'1 h, sûrement des rush) : ${g.ignored.join(", ")}` : "")
      : "";
  $("#guide-rebuild").disabled = data.guide_busy;
  $("#guide-text").innerHTML = g ? miniMarkdown(g.text) : "";
  const examples = (g && g.examples) || [];
  $("#guide-examples-box").classList.toggle("hidden", !examples.length);
  $("#guide-examples").innerHTML = examples
    .map((e) => `<li><span class="badge">${esc(e.video || "")} ${esc(e.time || "")}</span> « ${esc(e.quote)} » <span class="muted">— ${esc(e.why_kept)}${e.effects ? ` · ${esc(e.effects)}` : ""}</span></li>`)
    .join("");
  const suggested = (g && g.suggested) || { values: {}, sources: {} };
  const keys = Object.keys(suggested.values || {});
  $("#guide-suggest-box").classList.toggle("hidden", !keys.length);
  if (keys.length) {
    api("/api/style").then((current) => {
      const show = (v) => (typeof v === "boolean" ? (v ? "oui" : "non") : v);
      $("#guide-suggest").innerHTML = keys
        .map((k) => `<tr><td>${esc(SUGGEST_LABELS[k] || k)}</td><td>${esc(show(current[k]))}</td><td><b>${esc(show(suggested.values[k]))}</b></td><td class="muted">${esc(suggested.sources[k] || "")}</td></tr>`)
        .join("");
    });
  }
  $("#ref-lib-hint").textContent = data.claude
    ? "Les bruitages ne sont reconnus que s'ils sont dans la bibliothèque (onglet Bibliothèque)."
    : "⚠️ Sans clé Claude (Réglages), KrokCut ne tirera que des mesures de ces vidéos (rythme, bruitages), pas le style.";
}

async function loadRefDetails(id) {
  const box = $(`#ref-details-${CSS.escape(id)}`);
  if (!box) return;
  let r;
  try { r = await api(`/api/references/${encodeURIComponent(id)}`); } catch (_) { return; }
  const a = r.analysis;
  if (!a) { box.innerHTML = "<p class='muted'>Pas encore d'analyse.</p>"; return; }
  const section = (title, text) => (text ? `<h4>${title}</h4><p>${esc(text)}</p>` : "");
  const top = (r.metrics.sfx_top || []).map(([asset, count]) => `<span class="badge">${esc(asset)} ×${count}</span>`).join(" ");
  box.innerHTML = [
    section("Résumé", a.summary),
    section("Structure", a.structure),
    section("Ce qui est gardé", a.humor),
    section("Montage à l'image", a.editing),
    section("Sound design", a.sound_design),
    top ? `<h4>Bruitages reconnus</h4><p>${top}</p>` : "",
    a.rules && a.rules.length ? `<h4>Règles</h4><ul>${a.rules.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "",
    a.examples && a.examples.length
      ? `<h4>Moments représentatifs</h4><ul>${a.examples.map((e) => `<li><span class="badge">${esc(e.time)}</span> « ${esc(e.quote)} » <span class="muted">— ${esc(e.why_kept)}${e.effects ? ` · ${esc(e.effects)}` : ""}</span></li>`).join("")}</ul>`
      : "",
  ].join("") || "<p class='muted'>Analyse vide.</p>";
}

async function addReferencePaths(paths) {
  if (!paths.length) return;
  try {
    const res = await api("/api/references", { method: "POST", body: { paths } });
    const fresh = res.added.length - res.duplicates.length;
    const parts = [];
    if (fresh > 0) parts.push(`${fresh} vidéo${fresh > 1 ? "s" : ""} ajoutée${fresh > 1 ? "s" : ""} : analyse lancée.`);
    if (res.duplicates.length) parts.push(`Déjà dans la liste : ${res.duplicates.join(", ")}.`);
    toast(parts.join(" "));
  } catch (err) {
    toast(err.message, true);
  }
  loadReferences();
  checkReferences();
}

function renderRefUploads() {
  $("#ref-uploads").innerHTML = state.refUploads
    .filter((u) => u.progress < 1)
    .map((u) => `<li><span>${esc(u.name)}</span><span class="progress">${Math.round(u.progress * 100)} %</span></li>`)
    .join("");
}

const refDrop = $("#ref-drop");
refDrop.addEventListener("dragover", (e) => { e.preventDefault(); refDrop.classList.add("over"); });
refDrop.addEventListener("dragleave", () => refDrop.classList.remove("over"));
refDrop.addEventListener("drop", async (e) => {
  e.preventDefault();
  refDrop.classList.remove("over");
  for (const file of e.dataTransfer.files) {
    const entry = { name: file.name, progress: 0 };
    state.refUploads.push(entry);
    renderRefUploads();
    try {
      const path = await putFile(file, "references", (p) => { entry.progress = p; renderRefUploads(); });
      entry.progress = 1;
      renderRefUploads();
      await addReferencePaths([path]);
    } catch (err) {
      entry.progress = 1;
      renderRefUploads();
      toast(`Envoi impossible : ${err.message}`, true);
    }
  }
});
$("#ref-browse").addEventListener("click", () => openBrowser(addReferencePaths));
$("#guide-rebuild").addEventListener("click", async () => {
  await api("/api/guide/rebuild", { method: "POST" });
  loadReferences();
});
$("#guide-apply").addEventListener("click", async () => {
  if (!confirm("Remplacer ces réglages du style par défaut (utilisé pour les nouveaux épisodes) ?")) return;
  try {
    await api("/api/guide/apply", { method: "POST" });
    toast("Style par défaut mis à jour : il s'appliquera aux prochains épisodes.");
    loadReferences();
  } catch (err) {
    toast(err.message, true);
  }
});
