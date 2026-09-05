import Link from "next/link";
import { Section } from "@/components/ui/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";
import { ArrowRight } from "@/components/ui/Button";
import { BrandBoard, BoardNotes } from "@/components/cases/BrandBoard";
import { caseStudies } from "@/data/case-studies";

/** Étude de cas mise en avant sur la page d’accueil. */
export function FeaturedCase() {
  const study = caseStudies.find((c) => c.featured) ?? caseStudies[0];

  return (
    <Section tone="white" id="preuve">
      <Reveal>
        <SectionHeading
          eyebrow="La preuve"
          title="Ce que ça donne quand le système est appliqué"
          lead="Une céramiste dont le travail était remarquable et la marque illisible. Six semaines plus tard : un positionnement tranché, une identité applicable et un catalogue en ligne."
        />
      </Reveal>

      <Reveal delay={0.08} className="mt-12">
        <div className="grid gap-10 lg:grid-cols-2 lg:gap-12">
          <div>
            <BrandBoard snapshot={study.before} client={study.client} variant="before" />
            <BoardNotes snapshot={study.before} variant="before" />
          </div>
          <div>
            <BrandBoard snapshot={study.after} client={study.client} variant="after" />
            <BoardNotes snapshot={study.after} variant="after" />
          </div>
        </div>
      </Reveal>

      <Reveal delay={0.12} className="mt-12">
        <div className="rounded-lg border border-ink-200 bg-pearl/60 p-7 sm:p-9">
          <dl className="grid gap-8 sm:grid-cols-4">
            {study.metrics.map((m) => (
              <div key={m.label}>
                <dd className="font-display text-3xl font-bold tracking-[-0.03em] text-ink-900 sm:text-4xl">
                  {m.value}
                </dd>
                <dt className="mt-1.5 text-[14px] leading-snug text-ink-600">
                  {m.label}
                </dt>
                {m.detail && (
                  <p className="mt-1 text-[13px] text-ink-400">{m.detail}</p>
                )}
              </div>
            ))}
          </dl>

          <Link
            href={`/etudes-de-cas/${study.slug}`}
            className="group mt-8 inline-flex items-center gap-2 font-display text-[16px] font-semibold text-ink-900"
          >
            Voir l’étude complète — {study.client}
            <ArrowRight className="transition-transform duration-300 group-hover:translate-x-1" />
          </Link>
        </div>
      </Reveal>
    </Section>
  );
}
