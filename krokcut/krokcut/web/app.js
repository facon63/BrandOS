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
$$(".tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    $$(".view").forEach((v) => v.classList.toggle("hidden", v.id !== `view-${tab.dataset.view}`));
    if (tab.dataset.view === "library") loadLibrary();
    if (tab.dataset.view === "settings") loadSettings();
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

function uploadFile(file, pov) {
  const entry = { name: file.name, progress: 0 };
  state.files[pov].push(entry);
  renderFiles();
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `/api/upload/${encodeURIComponent(file.name)}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        entry.progress = e.loaded / e.total;
        renderFiles();
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        entry.path = JSON.parse(xhr.responseText).path;
        entry.progress = 1;
        renderFiles();
        resolve();
      } else reject(new Error(xhr.responseText));
    };
    xhr.onerror = () => reject(new Error("Échec de l'envoi"));
    xhr.send(file);
  });
}

$$(".dropzone").forEach((zone) => {
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
let browsePov = "a";
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
  b.addEventListener("click", () => {
    browsePov = b.dataset.browse;
    $("#browser").showModal();
    browseTo(localStorage.getItem("krokcut-last-dir") || "");
  })
);
$("#br-go").addEventListener("click", () => browseTo($("#br-path").value));
$("#br-add").addEventListener("click", () => {
  const picked = $$("#br-list input:checked").map((i) => i.value);
  picked.forEach((p) => state.files[browsePov].push({ name: p, path: p }));
  try { localStorage.setItem("krokcut-last-dir", $("#br-path").value); } catch (_) { /* stockage indisponible */ }
  renderFiles();
  $("#browser").close();
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

checkClaude();
loadProjects();
