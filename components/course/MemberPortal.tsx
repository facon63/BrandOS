"use client";

import { useState } from "react";
import Link from "next/link";
import { VideoPlayerMock } from "./VideoPlayerMock";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Badge } from "@/components/ui/Badge";
import { course, courseProgress } from "@/data/courses";
import type { Lesson } from "@/lib/types";
import { cx, formatDuration, formatLessonDuration } from "@/lib/format";

/* ============================================================================
   Espace membre — MOCK.
   TODO (phase 2) :
   - remplacer l’accès simulé par une vraie session authentifiée ;
   - remplacer les statuts de leçon par la progression réelle de l’utilisateur ;
   - brancher le lecteur sur l’hébergeur vidéo.
   Les cases de progression sont modifiables ici pour valider l’ergonomie, mais
   rien n’est persisté : un rechargement remet l’état d’origine.
   ========================================================================= */

export function MemberPortal() {
  const [activeModuleId, setActiveModuleId] = useState(course.modules[1].id);
  const [activeLessonId, setActiveLessonId] = useState(course.modules[1].lessons[1].id);
  const [statuses, setStatuses] = useState<Record<string, Lesson["status"]>>(() =>
    Object.fromEntries(
      course.modules.flatMap((m) => m.lessons.map((l) => [`${m.id}-${l.id}`, l.status])),
    ),
  );

  const activeModule = course.modules.find((m) => m.id === activeModuleId)!;
  const activeLesson =
    activeModule.lessons.find((l) => l.id === activeLessonId) ?? activeModule.lessons[0];

  const global = courseProgress();

  const toggle = (moduleId: string, lessonId: string) =>
    setStatuses((s) => {
      const key = `${moduleId}-${lessonId}`;
      return { ...s, [key]: s[key] === "done" ? "todo" : "done" };
    });

  const doneCount = Object.values(statuses).filter((s) => s === "done").length;
  const livePercent = Math.round((doneCount / global.total) * 100);

  /* La progression par module est recalculée depuis l’état courant : cocher une
     leçon doit mettre à jour la barre du module en même temps que la globale. */
  const percentFor = (moduleId: string) => {
    const mod = course.modules.find((m) => m.id === moduleId)!;
    const done = mod.lessons.filter(
      (l) => statuses[`${moduleId}-${l.id}`] === "done",
    ).length;
    return Math.round((done / mod.lessons.length) * 100);
  };

  return (
    <div className="grid gap-8 lg:grid-cols-[19rem_1fr] lg:gap-10">
      {/* --- Sidebar modules ------------------------------------------- */}
      <aside className="lg:sticky lg:top-24 lg:self-start">
        <div className="rounded-lg border border-ink-200 bg-white p-5">
          <p className="font-display text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">
            Progression globale
          </p>
          <div className="mt-2 flex items-baseline justify-between">
            <p className="font-display text-3xl font-bold tracking-[-0.03em] text-ink-900">
              {livePercent}
              <span className="text-crown">%</span>
            </p>
            <p className="text-[13px] text-ink-500">
              {doneCount} / {global.total} leçons
            </p>
          </div>
          <ProgressBar value={livePercent} className="mt-3" label="Progression globale" />
        </div>

        <nav aria-label="Modules de la formation" className="mt-4">
          <ul className="flex flex-col gap-1.5">
            {course.modules.map((m) => {
              const active = m.id === activeModuleId;
              const percent = percentFor(m.id);
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveModuleId(m.id);
                      setActiveLessonId(m.lessons[0].id);
                    }}
                    aria-current={active ? "true" : undefined}
                    className={cx(
                      "w-full rounded-md border px-4 py-3.5 text-left transition-all duration-200",
                      active
                        ? "border-obsidian bg-obsidian text-white"
                        : "border-ink-200 bg-white hover:border-ink-300",
                    )}
                  >
                    <span className="flex items-center gap-2.5">
                      <span
                        className={cx(
                          "font-display text-[12px] font-bold",
                          active ? "text-crown" : "text-ink-400",
                        )}
                      >
                        {String(m.index).padStart(2, "0")}
                      </span>
                      <span
                        className={cx(
                          "flex-1 font-display text-[15px] font-semibold tracking-[-0.01em]",
                          active ? "text-white" : "text-ink-900",
                        )}
                      >
                        {m.title}
                      </span>
                      <span className={cx("text-[12px]", active ? "text-white/50" : "text-ink-400")}>
                        {percent}%
                      </span>
                    </span>
                    <ProgressBar
                      value={percent}
                      tone={active ? "crown" : "teal"}
                      className={cx("mt-2.5", active && "bg-white/15")}
                      label={`Progression du module ${m.title}`}
                    />
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>

      {/* --- Zone principale -------------------------------------------- */}
      <div>
        <VideoPlayerMock
          module={`Module ${activeModule.index} — ${activeModule.title}`}
          title={activeLesson.title}
          duration={activeLesson.duration}
        />

        <div className="mt-8 grid gap-8 xl:grid-cols-[1.35fr_0.65fr]">
          <section aria-labelledby="lecons-heading">
            <div className="flex items-baseline justify-between gap-4">
              <h2
                id="lecons-heading"
                className="font-display text-xl font-bold tracking-[-0.02em] text-ink-900"
              >
                Leçons du module
              </h2>
              <p className="text-[13px] text-ink-500">
                {formatDuration(
                  activeModule.lessons.reduce((n, l) => n + l.duration, 0),
                )}
              </p>
            </div>

            <p className="mt-2 text-[15px] leading-relaxed text-ink-600">
              {activeModule.promise}
            </p>

            <ul className="mt-6 divide-y divide-ink-200 overflow-hidden rounded-lg border border-ink-200">
              {activeModule.lessons.map((l, i) => {
                const key = `${activeModule.id}-${l.id}`;
                const status = statuses[key];
                const selected = l.id === activeLessonId;

                return (
                  <li
                    key={l.id}
                    className={cx(
                      "flex items-center gap-3 px-4 py-3.5 transition-colors sm:px-5",
                      selected ? "bg-crown-soft/60" : "bg-white hover:bg-pearl/60",
                    )}
                  >
                    <label className="flex shrink-0 cursor-pointer items-center">
                      <input
                        type="checkbox"
                        checked={status === "done"}
                        onChange={() => toggle(activeModule.id, l.id)}
                        className="h-4 w-4 cursor-pointer accent-teal"
                      />
                      <span className="sr-only">
                        Marquer « {l.title} » comme {status === "done" ? "à faire" : "vue"}
                      </span>
                    </label>

                    <button
                      type="button"
                      onClick={() => setActiveLessonId(l.id)}
                      className="flex flex-1 items-center gap-3 text-left"
                    >
                      <span className="w-5 shrink-0 font-display text-[12px] tabular-nums text-ink-400">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span
                        className={cx(
                          "flex-1 text-[15px] leading-snug",
                          status === "done" ? "text-ink-500" : "text-ink-900",
                          selected && "font-medium",
                        )}
                      >
                        {l.title}
                      </span>
                      <LessonStatus status={status} selected={selected} />
                      <span className="w-14 shrink-0 text-right text-[13px] tabular-nums text-ink-500">
                        {formatLessonDuration(l.duration)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>

          <aside aria-labelledby="ressources-heading">
            <h2
              id="ressources-heading"
              className="font-display text-xl font-bold tracking-[-0.02em] text-ink-900"
            >
              Ressources
            </h2>
            <p className="mt-2 text-[15px] leading-relaxed text-ink-600">
              Les fichiers rattachés à ce module.
            </p>

            <ul className="mt-6 flex flex-col gap-2.5">
              {activeModule.resources.map((r) => (
                <li key={r.label}>
                  {/* TODO (phase 2) : lien vers le fichier réel. */}
                  <button
                    type="button"
                    className="flex w-full items-center gap-3 rounded-md border border-ink-200 bg-white px-4 py-3.5 text-left transition-colors hover:border-ink-300 hover:bg-pearl/50"
                  >
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-pearl font-display text-[10px] font-bold uppercase tracking-[0.06em] text-teal">
                      {r.format}
                    </span>
                    <span className="flex-1 text-[15px] leading-snug text-ink-800">
                      {r.label}
                    </span>
                    <svg viewBox="0 0 20 20" className="h-4 w-4 shrink-0 text-ink-400" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M10 4v9m0 0 3.5-3.5M10 13 6.5 9.5M4 16h12" />
                    </svg>
                  </button>
                </li>
              ))}
            </ul>

            <div className="mt-8 rounded-lg border border-ink-200 bg-pearl/60 p-5">
              <Badge tone="teal">Inclus avec la formation</Badge>
              <p className="mt-3 text-[15px] leading-relaxed text-ink-700">
                Le Kit BrandOS & Roadmap est rattaché à ton compte. Les livrables
                de chaque module s’y déposent au fur et à mesure.
              </p>
              <Link
                href="/produits/kit-brandos-roadmap"
                className="mt-3 inline-block font-display text-[14px] font-semibold text-teal hover:text-teal-hover"
              >
                Ouvrir le kit
              </Link>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function LessonStatus({
  status,
  selected,
}: {
  status: Lesson["status"];
  selected: boolean;
}) {
  if (selected) return <Badge tone="crown">En cours</Badge>;
  if (status === "done")
    return (
      <span className="hidden text-[12px] font-medium text-teal sm:inline">Vue</span>
    );
  if (status === "in-progress") return <Badge tone="teal">Reprise</Badge>;
  return <span className="hidden text-[12px] text-ink-400 sm:inline">À faire</span>;
}
