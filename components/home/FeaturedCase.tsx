import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";
import { ArrowRight } from "@/components/ui/Button";
import { Counter } from "@/components/motion/Counter";
import { BrandBoard, BoardNotes } from "@/components/cases/BrandBoard";
import { caseStudies } from "@/data/case-studies";

/** Étude de cas mise en avant sur la page d'accueil. */
export function FeaturedCase() {
  const study = caseStudies.find((c) => c.featured) ?? caseStudies[0];

  return (
    <section id="preuve" className="relative py-24 sm:py-32">
      <Container>
        <Reveal>
          <SectionHeading
            tone="dark"
            eyebrow="La preuve"
            title="Ce que ça donne quand le système est appliqué"
            lead="Une céramiste dont le travail était remarquable et la marque illisible. Six semaines plus tard : un positionnement tranché, une identité applicable et un catalogue en ligne."
          />
        </Reveal>

        <Reveal delay={0.1} className="mt-14">
          <div className="grid gap-10 lg:grid-cols-2 lg:gap-12">
            <div>
              <BrandBoard snapshot={study.before} client={study.client} variant="before" />
              <BoardNotes snapshot={study.before} variant="before" tone="dark" />
            </div>
            <div>
              <BrandBoard snapshot={study.after} client={study.client} variant="after" />
              <BoardNotes snapshot={study.after} variant="after" tone="dark" />
            </div>
          </div>
        </Reveal>

        <Reveal delay={0.16} className="mt-12">
          <div className="rounded-xl border border-white/12 bg-charcoal/50 p-8 backdrop-blur-md sm:p-10">
            <dl className="grid gap-8 sm:grid-cols-4">
              {study.metrics.map((m) => (
                <div key={m.label}>
                  <dd className="font-display text-3xl font-bold tracking-[-0.03em] text-white sm:text-4xl">
                    <Counter value={m.value} />
                  </dd>
                  <dt className="mt-2 text-[14px] leading-snug text-white/55">
                    {m.label}
                  </dt>
                  {m.detail && (
                    <p className="mt-1 text-[13px] text-white/30">{m.detail}</p>
                  )}
                </div>
              ))}
            </dl>

            <Link
              href={`/etudes-de-cas/${study.slug}`}
              className="group mt-9 inline-flex items-center gap-2 font-display text-[16px] font-semibold text-white"
            >
              Voir l’étude complète — {study.client}
              <ArrowRight className="transition-transform duration-300 group-hover:translate-x-1.5" />
            </Link>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
