import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { PageHero } from "@/components/layout/PageHero";
import { Section } from "@/components/ui/Section";
import { Reveal } from "@/components/ui/Reveal";
import { Eyebrow } from "@/components/ui/Badge";
import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { CtaBanner } from "@/components/marketing/CtaBanner";
import { course } from "@/data/courses";
import { formatDuration, formatLessonDuration } from "@/lib/format";

export const metadata: Metadata = {
  title: "Programme détaillé",
  description:
    "Le détail des 5 modules et 22 leçons de la formation BrandOS : promesse de chaque module, leçons, durées et ressources téléchargeables.",
};

export default function ProgrammePage() {
  return (
    <PageShell headerTone="dark">
      <PageHero
        eyebrow="Formation — programme"
        title="Le parcours, leçon par leçon"
        lead={`${course.modules.length} modules, ${course.totalLessons} leçons, ${formatDuration(course.totalDuration)} de vidéo. Chaque module ouvre sur une promesse précise et se ferme sur un livrable.`}
        crumbs={[
          { href: "/", label: "Accueil" },
          { href: "/formation", label: "Formation" },
          { label: "Programme" },
        ]}
      >
        <ButtonLink href="/tarifs" size="lg">
          Rejoindre la formation
          <ArrowRight />
        </ButtonLink>
      </PageHero>

      <Section tone="white">
        <div className="flex flex-col gap-16 sm:gap-20">
          {course.modules.map((m, index) => {
            const minutes = m.lessons.reduce((n, l) => n + l.duration, 0);

            return (
              <Reveal key={m.id}>
                <article className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:gap-14">
                  <div>
                    <div className="flex items-baseline gap-4">
                      <span className="font-display text-5xl font-bold tracking-[-0.04em] text-ink-200">
                        {String(m.index).padStart(2, "0")}
                      </span>
                      <div>
                        <Eyebrow>Module {m.index}</Eyebrow>
                        <h2 className="mt-1.5 font-display text-2xl font-bold tracking-[-0.025em] text-ink-900 sm:text-3xl">
                          {m.title}
                        </h2>
                      </div>
                    </div>

                    <p className="mt-5 border-l-2 border-crown pl-4 font-display text-[16px] font-semibold leading-snug text-ink-900">
                      {m.promise}
                    </p>

                    <p className="mt-5 text-[16px] leading-relaxed text-ink-600">
                      {m.description}
                    </p>

                    <p className="mt-6 text-[14px] text-ink-500">
                      {m.lessons.length} leçons · {formatDuration(minutes)}
                    </p>

                    <div className="mt-5 flex flex-wrap gap-2">
                      {m.resources.map((r) => (
                        <span
                          key={r.label}
                          className="inline-flex items-center gap-1.5 rounded-full border border-ink-200 px-3 py-1 text-[12px] text-ink-600"
                        >
                          <span className="font-display text-[10px] font-bold uppercase tracking-[0.1em] text-teal">
                            {r.format}
                          </span>
                          {r.label}
                        </span>
                      ))}
                    </div>
                  </div>

                  <ol className="divide-y divide-ink-200 overflow-hidden rounded-lg border border-ink-200">
                    {m.lessons.map((l, i) => (
                      <li
                        key={l.id}
                        className="flex items-baseline gap-4 px-5 py-4 transition-colors hover:bg-pearl/60 sm:px-6"
                      >
                        <span className="w-6 shrink-0 font-display text-[12px] font-semibold tabular-nums text-ink-400">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span className="flex-1 text-[16px] leading-snug text-ink-800">
                          {l.title}
                          {l.preview && (
                            <span className="ml-2 inline-block rounded-full bg-teal-soft px-2 py-0.5 text-[11px] font-semibold text-teal-hover">
                              Aperçu gratuit
                            </span>
                          )}
                        </span>
                        <span className="shrink-0 text-[13px] tabular-nums text-ink-500">
                          {formatLessonDuration(l.duration)}
                        </span>
                      </li>
                    ))}
                  </ol>
                </article>

                {index < course.modules.length - 1 && (
                  <div className="mt-16 h-px bg-ink-200 sm:mt-20" aria-hidden="true" />
                )}
              </Reveal>
            );
          })}
        </div>
      </Section>

      <CtaBanner
        title="Le programme est complet. Il ne manque que toi."
        lead={`${course.totalLessons} leçons, ${formatDuration(course.totalDuration)} de vidéo, le Kit BrandOS offert et l’accès à vie. Garantie 30 jours.`}
        primary={{ href: "/tarifs", label: "Rejoindre la formation" }}
        secondary={{ href: "/espace-membre", label: "Voir l’espace membre" }}
      />
    </PageShell>
  );
}
