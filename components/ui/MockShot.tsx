"use client";

import { motion, useInView, useReducedMotion } from "framer-motion";
import { useRef } from "react";
import { cx } from "@/lib/format";
import type { MockVisual } from "@/lib/types";

/* ============================================================================
   TODO (phase 2) — remplacer par de vraies captures produit.
   En attendant, on rend des maquettes stylisées plutôt que des rectangles
   gris : elles montrent la structure réelle du produit (dashboard, bases de
   données, checklist, palette, prompts) et respectent la charte.
   Aucune donnée affichée ici n’est réelle.
   ========================================================================= */

export function MockShot({
  visual,
  className,
  compact = false,
}: {
  visual: MockVisual;
  className?: string;
  compact?: boolean;
}) {
  return (
    <figure
      className={cx(
        "overflow-hidden rounded-lg border border-ink-200 bg-white",
        className,
      )}
    >
      <ChromeBar label={visual.caption} />
      <div className={cx("bg-pearl/60", compact ? "p-4" : "p-5 sm:p-6")}>
        {visual.kind === "dashboard" && <DashboardMock />}
        {visual.kind === "database" && <DatabaseMock />}
        {visual.kind === "checklist" && <ChecklistMock />}
        {visual.kind === "palette" && <PaletteMock />}
        {visual.kind === "prompts" && <PromptsMock />}
        {visual.kind === "cover" && <CoverMock caption={visual.caption} />}
      </div>
      <figcaption className="border-t border-ink-200 px-4 py-2.5 text-[12px] text-ink-500">
        {visual.caption}
        <span className="ml-1.5 text-ink-400">— aperçu de démonstration</span>
      </figcaption>
    </figure>
  );
}

function ChromeBar({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 border-b border-ink-200 bg-white px-4 py-2.5">
      <span className="h-2 w-2 rounded-full bg-ink-200" />
      <span className="h-2 w-2 rounded-full bg-ink-200" />
      <span className="h-2 w-2 rounded-full bg-ink-200" />
      <span className="ml-2 truncate font-display text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-400">
        {label}
      </span>
    </div>
  );
}

/* --- Dashboard : la vue signature du Kit ----------------------------------
   `animated` fait se remplir les barres à l'entrée dans le viewport : le
   dashboard se « charge » sous les yeux du visiteur au lieu d'être un décor
   figé. */
export function DashboardMock({
  className,
  animated = false,
}: {
  className?: string;
  animated?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const inView = useInView(ref, { once: true, margin: "-10%" });
  const play = animated && !reduced;
  const fill = (percent: number) => (play ? (inView ? percent : 0) : percent);

  const pillars = [
    { label: "Positionnement", percent: 100 },
    { label: "Identité visuelle", percent: 72 },
    { label: "Voix & messages", percent: 45 },
    { label: "Roadmap", percent: 18 },
  ];

  return (
    <div ref={ref} className={cx("flex flex-col gap-4", className)}>
      <div className="rounded-md border border-ink-200 bg-white p-4">
        <div className="flex items-baseline justify-between">
          <p className="font-display text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">
            Progression globale
          </p>
          <p className="font-display text-2xl font-bold tracking-[-0.03em] text-ink-900">
            59<span className="text-crown">%</span>
          </p>
        </div>
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
          <motion.div
            className="h-full rounded-full bg-crown"
            initial={false}
            animate={{ width: `${fill(59)}%` }}
            transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
          />
        </div>
        <p className="mt-3 text-[12px] text-ink-500">
          Prochaine action —{" "}
          <span className="font-medium text-ink-900">
            Tester la palette en contraste réel
          </span>
        </p>
      </div>

      <div className="grid gap-2.5">
        {pillars.map((p, i) => (
          <div
            key={p.label}
            className="flex min-w-0 items-center gap-3 rounded-md border border-ink-200 bg-white px-3.5 py-2.5"
          >
            <span className="w-[6.5rem] shrink-0 truncate text-[12px] font-medium text-ink-700">
              {p.label}
            </span>
            <span className="h-1 min-w-0 flex-1 overflow-hidden rounded-full bg-ink-100">
              <motion.span
                className={cx(
                  "block h-full rounded-full",
                  p.percent === 100 ? "bg-teal" : "bg-crown",
                )}
                initial={false}
                animate={{ width: `${fill(p.percent)}%` }}
                transition={{
                  duration: 1,
                  delay: 0.15 + i * 0.1,
                  ease: [0.16, 1, 0.3, 1],
                }}
              />
            </span>
            <span className="w-9 shrink-0 text-right font-display text-[11px] font-semibold text-ink-500">
              {p.percent}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* --- Base de données Notion ----------------------------------------------- */
function DatabaseMock() {
  const rows = [
    { name: "Promesse", tag: "Validé", tone: "teal" as const },
    { name: "Cible primaire", tag: "Validé", tone: "teal" as const },
    { name: "Trois refus", tag: "En cours", tone: "crown" as const },
    { name: "Preuves", tag: "À faire", tone: "neutral" as const },
    { name: "Concurrence", tag: "À faire", tone: "neutral" as const },
  ];

  return (
    <div className="overflow-hidden rounded-md border border-ink-200 bg-white">
      <div className="flex items-center gap-4 border-b border-ink-200 px-4 py-2.5 font-display text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-400">
        <span className="flex-1">Champ</span>
        <span className="w-20">Statut</span>
      </div>
      {rows.map((r) => (
        <div
          key={r.name}
          className="flex items-center gap-4 border-b border-ink-100 px-4 py-2.5 last:border-b-0"
        >
          <span className="flex-1 text-[13px] text-ink-800">{r.name}</span>
          <span className="w-20">
            <span
              className={cx(
                "inline-block rounded-full px-2 py-0.5 text-[11px] font-medium",
                r.tone === "teal" && "bg-teal-soft text-teal-hover",
                r.tone === "crown" && "bg-crown-soft text-ink-800",
                r.tone === "neutral" && "bg-ink-100 text-ink-500",
              )}
            >
              {r.tag}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

/* --- Checklist Launch-Ready ------------------------------------------------ */
function ChecklistMock() {
  const items = [
    { label: "Écrire la promesse en < 20 mots", done: true },
    { label: "Valider la promesse auprès de 3 personnes", done: true },
    { label: "Verrouiller 5 couleurs, testées en contraste", done: true },
    { label: "Choisir une police, deux graisses", done: false },
    { label: "Rédiger la liste des mots bannis", done: false },
    { label: "Produire 12 gabarits de publication", done: false },
  ];

  return (
    <div className="rounded-md border border-ink-200 bg-white p-4">
      <p className="mb-3 font-display text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">
        Phase 1 — Clarifier · 3 / 6
      </p>
      <ul className="flex flex-col gap-2.5">
        {items.map((i) => (
          <li key={i.label} className="flex items-start gap-2.5">
            <span
              className={cx(
                "mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-[4px] border",
                i.done ? "border-teal bg-teal text-white" : "border-ink-300",
              )}
              aria-hidden="true"
            >
              {i.done && (
                <svg viewBox="0 0 12 12" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2.5 6.5 L5 9 L9.5 3.5" />
                </svg>
              )}
            </span>
            <span
              className={cx(
                "text-[13px] leading-snug",
                i.done ? "text-ink-400 line-through" : "text-ink-800",
              )}
            >
              {i.label}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* --- Générateur de palette ------------------------------------------------- */
function PaletteMock() {
  const swatches = [
    { hex: "#141414", name: "Fondation" },
    { hex: "#FFD600", name: "Accent" },
    { hex: "#3399A6", name: "Secondaire" },
    { hex: "#F0F0F2", name: "Surface" },
    { hex: "#FFFFFF", name: "Neutre" },
  ];

  return (
    <div className="rounded-md border border-ink-200 bg-white p-4">
      <div className="grid grid-cols-5 gap-2">
        {swatches.map((s) => (
          <div key={s.hex} className="flex flex-col gap-1.5">
            <span
              className="block aspect-square rounded-[6px] border border-ink-200"
              style={{ background: s.hex }}
            />
            <span className="truncate text-[10px] font-medium text-ink-500">
              {s.name}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-between rounded-[6px] bg-pearl px-3 py-2">
        <span className="text-[11px] text-ink-600">Contraste texte / fond</span>
        <span className="rounded-full bg-teal-soft px-2 py-0.5 text-[11px] font-semibold text-teal-hover">
          AA validé
        </span>
      </div>
    </div>
  );
}

/* --- Bibliothèque de prompts ---------------------------------------------- */
function PromptsMock() {
  const prompts = [
    "Réécrire ma bio en gardant ma voix",
    "Générer 10 accroches à partir de ma promesse",
    "Transformer une étude de cas en post",
    "Rédiger ma page à propos en 3 blocs",
  ];

  return (
    <div className="grid gap-2.5">
      {prompts.map((p, i) => (
        <div
          key={p}
          className="rounded-md border border-ink-200 bg-white px-3.5 py-3"
        >
          <div className="mb-1.5 flex items-center gap-2">
            <span className="font-display text-[10px] font-bold text-teal">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="rounded-full bg-ink-100 px-2 py-0.5 text-[10px] font-medium text-ink-500">
              Voix
            </span>
          </div>
          <p className="text-[13px] leading-snug text-ink-800">{p}</p>
        </div>
      ))}
    </div>
  );
}

/* --- Couverture générique -------------------------------------------------- */
function CoverMock({ caption }: { caption: string }) {
  return (
    <div className="grid aspect-[4/3] place-items-center rounded-md bg-obsidian p-6 text-center">
      <div>
        <p className="font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-crown">
          BrandOS
        </p>
        <p className="mt-2 font-display text-xl font-bold tracking-[-0.02em] text-white">
          {caption}
        </p>
        <p className="mt-3 text-[12px] text-white/45">
          Visuel de démonstration
        </p>
      </div>
    </div>
  );
}
