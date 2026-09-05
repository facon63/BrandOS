import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { PageShell } from "@/components/layout/PageShell";
import { Section } from "@/components/ui/Section";
import { Container } from "@/components/ui/Container";
import { Breadcrumbs } from "@/components/ui/Breadcrumbs";
import { Eyebrow } from "@/components/ui/Badge";
import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { Reveal } from "@/components/ui/Reveal";
import { BeforeAfterSlider } from "@/components/cases/BeforeAfterSlider";
import { BoardNotes } from "@/components/cases/BrandBoard";
import { CaseStudyCard } from "@/components/cases/CaseStudyCard";
import { caseStudies, getCaseStudy } from "@/data/case-studies";
import { getProduct } from "@/data/products";
import { course } from "@/data/courses";

export function generateStaticParams() {
  return caseStudies.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const study = getCaseStudy(slug);
  if (!study) return { title: "Étude de cas introuvable" };
  return {
    title: `${study.client} — ${study.headline}`,
    description: study.excerpt,
  };
}

export default async function CaseStudyPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const study = getCaseStudy(slug);
  if (!study) notFound();

  const others = caseStudies.filter((c) => c.slug !== study.slug).slice(0, 2);

  /* Destination du CTA final : le produit ou la formation réellement utilisés. */
  const ctaProduct =
    study.cta.kind === "product" ? getProduct(study.cta.slug) : undefined;
  const ctaHref = ctaProduct ? `/produits/${ctaProduct.slug}` : "/formation";
  const ctaTitle = ctaProduct ? ctaProduct.name : course.name;
  const ctaSubtitle = ctaProduct ? ctaProduct.tagline : course.tagline;

  return (
    <PageShell headerTone="dark">
      {/* --- Hero -------------------------------------------------------- */}
      <div className="on-dark relative overflow-hidden bg-obsidian pt-[72px] text-white">
        <div className="grid-lines pointer-events-none absolute inset-0" aria-hidden="true" />

        <Container className="relative py-14 sm:py-16">
          <Breadcrumbs
            tone="dark"
            className="mb-8"
            items={[
              { href: "/", label: "Accueil" },
              { href: "/etudes-de-cas", label: "Études de cas" },
              { label: study.client },
            ]}
          />

          <div className="grid gap-12 lg:grid-cols-[1fr_1fr] lg:gap-14">
            <div>
              <Eyebrow tone="crown">{study.sector}</Eyebrow>
              <h1 className="mt-4 text-4xl text-white sm:text-5xl">
                {study.client}
              </h1>
              <p className="mt-4 font-display text-xl font-semibold leading-snug tracking-[-0.02em] text-crown sm:text-2xl">
                {study.headline}
              </p>
              <p className="mt-5 max-w-xl text-lg leading-relaxed text-dark-muted">
                {study.excerpt}
              </p>

              <dl className="mt-9 flex flex-wrap gap-x-10 gap-y-6">
                {study.metrics.slice(0, 2).map((m) => (
                  <div key={m.label}>
                    <dd className="font-display text-4xl font-bold tracking-[-0.03em] text-white">
                      {m.value}
                    </dd>
                    <dt className="mt-1 text-[14px] text-dark-muted">{m.label}</dt>
                  </div>
                ))}
              </dl>
            </div>

            {/* Comparateur avant / après. */}
            <div className="rounded-lg border border-white/12 bg-white p-5 sm:p-6">
              <BeforeAfterSlider
                client={study.client}
                before={study.before}
                after={study.after}
              />
              <p className="mt-4 text-center text-[12px] text-ink-400">
                Planches reconstituées à partir des identités — visuels de démonstration
              </p>
            </div>
          </div>
        </Container>
      </div>

      {/* --- Contexte ---------------------------------------------------- */}
      <Section tone="white">
        <div className="grid gap-12 lg:grid-cols-[0.85fr_1.15fr] lg:gap-16">
          <Reveal>
            <Eyebrow>Le point de départ</Eyebrow>
            <h2 className="mt-3 text-3xl text-ink-900 sm:text-4xl">
              La situation avant
            </h2>
          </Reveal>

          <Reveal delay={0.08}>
            <div className="flex flex-col gap-5">
              {study.context.map((paragraph, i) => (
                <p key={i} className="text-[17px] leading-relaxed text-ink-700">
                  {paragraph}
                </p>
              ))}
            </div>

            <div className="mt-10 grid gap-8 sm:grid-cols-2">
              <div>
                <p className="font-display text-[12px] font-semibold uppercase tracking-[0.14em] text-ink-400">
                  Avant
                </p>
                <BoardNotes snapshot={study.before} variant="before" />
              </div>
              <div>
                <p className="font-display text-[12px] font-semibold uppercase tracking-[0.14em] text-teal">
                  Après
                </p>
                <BoardNotes snapshot={study.after} variant="after" />
              </div>
            </div>
          </Reveal>
        </div>
      </Section>

      {/* --- Méthode ------------------------------------------------------ */}
      <Section tone="obsidian">
        <Reveal>
          <Eyebrow tone="crown">La méthode</Eyebrow>
          <h2 className="mt-3 max-w-2xl text-3xl text-white sm:text-4xl">
            Les étapes du système réellement appliquées
          </h2>
        </Reveal>

        <ol className="mt-12 grid gap-5 sm:grid-cols-2">
          {study.method.map((step, i) => (
            <Reveal key={step.step} delay={i * 0.06}>
              <li className="h-full rounded-lg border border-white/12 bg-charcoal p-7">
                <span className="font-display text-[13px] font-bold text-crown">
                  {step.step}
                </span>
                <h3 className="mt-3 font-display text-xl font-bold tracking-[-0.02em] text-white">
                  {step.title}
                </h3>
                <p className="mt-3 text-[15px] leading-relaxed text-dark-muted">
                  {step.body}
                </p>
              </li>
            </Reveal>
          ))}
        </ol>
      </Section>

      {/* --- Résultats ---------------------------------------------------- */}
      <Section tone="pearl">
        <Reveal>
          <Eyebrow>Les résultats</Eyebrow>
          <h2 className="mt-3 text-3xl text-ink-900 sm:text-4xl">
            Ce que ça a changé
          </h2>
        </Reveal>

        <dl className="mt-11 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {study.metrics.map((m, i) => (
            <Reveal key={m.label} delay={i * 0.05}>
              <div className="h-full rounded-lg border border-ink-200 bg-white p-6">
                <dd className="font-display text-4xl font-bold tracking-[-0.03em] text-ink-900">
                  {m.value}
                </dd>
                <dt className="mt-2 text-[15px] leading-snug text-ink-700">
                  {m.label}
                </dt>
                {m.detail && (
                  <p className="mt-1.5 text-[13px] leading-snug text-ink-400">
                    {m.detail}
                  </p>
                )}
              </div>
            </Reveal>
          ))}
        </dl>

        <Reveal delay={0.1} className="mt-10">
          <figure className="rounded-lg border border-ink-200 bg-white p-8 sm:p-10">
            <blockquote className="font-display text-xl font-medium leading-snug tracking-[-0.015em] text-ink-900 sm:text-2xl">
              « {study.testimonial.quote} »
            </blockquote>
            <figcaption className="mt-6 flex items-center gap-3.5">
              <span
                aria-hidden="true"
                className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-obsidian font-display text-[14px] font-bold text-white"
              >
                {study.testimonial.initials}
              </span>
              <span>
                <span className="block font-display text-[15px] font-semibold text-ink-900">
                  {study.testimonial.author}
                </span>
                <span className="block text-[14px] text-ink-500">
                  {study.testimonial.role}
                </span>
              </span>
            </figcaption>
          </figure>
        </Reveal>
      </Section>

      {/* --- CTA ciblé ---------------------------------------------------- */}
      <Section tone="white">
        <div className="rounded-lg border border-ink-200 bg-pearl/60 p-8 sm:p-12">
          <div className="flex flex-wrap items-end justify-between gap-8">
            <div className="max-w-xl">
              <Eyebrow>Le module utilisé</Eyebrow>
              <h2 className="mt-3 text-2xl text-ink-900 sm:text-3xl">
                {ctaTitle}
              </h2>
              <p className="mt-3 text-[17px] leading-relaxed text-ink-600">
                {ctaSubtitle}
              </p>
            </div>
            <ButtonLink href={ctaHref} size="lg">
              {study.cta.label}
              <ArrowRight />
            </ButtonLink>
          </div>
        </div>
      </Section>

      {/* --- Autres études ------------------------------------------------ */}
      <Section tone="pearl">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h2 className="text-3xl text-ink-900 sm:text-4xl">Autres études de cas</h2>
          <Link
            href="/etudes-de-cas"
            className="font-display text-[15px] font-semibold text-teal hover:text-teal-hover"
          >
            Toutes les études
          </Link>
        </div>

        <div className="mt-9 grid gap-5 md:grid-cols-2">
          {others.map((s) => (
            <CaseStudyCard key={s.slug} study={s} />
          ))}
        </div>
      </Section>
    </PageShell>
  );
}
