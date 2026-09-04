import type { Metadata } from "next";
import Link from "next/link";
import { PageShell } from "@/components/layout/PageShell";
import { Section } from "@/components/ui/Section";
import { Container } from "@/components/ui/Container";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Badge, Eyebrow } from "@/components/ui/Badge";
import { Breadcrumbs } from "@/components/ui/Breadcrumbs";
import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { Reveal } from "@/components/ui/Reveal";
import { VideoPlayerMock } from "@/components/course/VideoPlayerMock";
import { ModuleTimeline } from "@/components/course/ModuleTimeline";
import { FaqBlock } from "@/components/marketing/FaqBlock";
import { TestimonialCarousel } from "@/components/marketing/TestimonialCarousel";
import { PeacockMarkStatic } from "@/components/brand/PeacockMark";
import { course } from "@/data/courses";
import { faq } from "@/data/faq";
import { testimonials } from "@/data/testimonials";
import { formatDuration, formatPrice } from "@/lib/format";

export const metadata: Metadata = {
  title: "Formation vidéo",
  description:
    "Cinq modules, vingt-deux leçons : positionnement, identité visuelle, voix, organisation, lancement. La méthode derrière le système BrandOS.",
};

const transformation = [
  {
    before: "Tu refais ton logo tous les trois mois",
    after: "Ton identité est verrouillée et documentée",
  },
  {
    before: "Ta bio ressemble à celle de tout le monde",
    after: "Ta promesse tient en une phrase que tes clients répètent",
  },
  {
    before: "Chaque publication rouvre le débat de la couleur",
    after: "Tu produis une semaine de contenu en une heure",
  },
  {
    before: "Ton site est bloqué sur la page d’accueil",
    after: "Ton lancement est daté, avec un critère de fin par étape",
  },
];

export default function FormationPage() {
  const formationFaq = faq.filter((f) => f.category === "Formation");
  const previewLesson = course.modules[0].lessons.find((l) => l.preview)!;

  return (
    <PageShell headerTone="dark">
      {/* --- Hero de vente ---------------------------------------------- */}
      <div className="on-dark relative overflow-hidden bg-obsidian pt-[72px] text-white">
        <div className="grid-lines pointer-events-none absolute inset-0" aria-hidden="true" />
        <PeacockMarkStatic
          monochrome
          className="pointer-events-none absolute -left-24 top-24 h-[24rem] w-auto text-white/[0.04]"
        />

        <Container className="relative py-16 sm:py-20">
          <Breadcrumbs
            tone="dark"
            className="mb-8"
            items={[{ href: "/", label: "Accueil" }, { label: "Formation" }]}
          />

          <div className="grid items-start gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
            <div>
              <Eyebrow tone="crown">Module 02 — Formation vidéo</Eyebrow>
              <h1 className="mt-4 text-4xl text-white sm:text-5xl lg:text-[3.5rem]">
                Construis ta marque étape par étape
              </h1>
              <p className="mt-5 max-w-xl text-lg leading-relaxed text-dark-muted">
                {course.totalLessons} leçons réparties en {course.modules.length}{" "}
                modules, {formatDuration(course.totalDuration)} de vidéo. Chaque
                étape se termine par un livrable — pas par une bonne intention.
              </p>

              <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center">
                <ButtonLink href="/tarifs" size="lg">
                  Rejoindre la formation
                  <ArrowRight />
                </ButtonLink>
                <p className="font-display text-[15px] text-white/50">
                  <span className="text-2xl font-bold text-white">
                    {formatPrice(course.price)}
                  </span>
                  {course.compareAtPrice && (
                    <span className="ml-2 line-through">
                      {formatPrice(course.compareAtPrice)}
                    </span>
                  )}
                </p>
              </div>

              <p className="mt-5 text-[14px] text-white/40">
                Accès à vie · Kit BrandOS offert · Garantie 30 jours
              </p>
            </div>

            <div>
              <VideoPlayerMock
                module="Aperçu gratuit — Module 01"
                title={previewLesson.title}
                duration={previewLesson.duration}
              />
              <p className="mt-3 text-center text-[12px] text-white/30">
                Lecteur de démonstration — l’hébergement vidéo arrive à la mise en ligne
              </p>
            </div>
          </div>
        </Container>
      </div>

      {/* --- Avant / après ---------------------------------------------- */}
      <Section tone="white">
        <Reveal>
          <SectionHeading
            eyebrow="La transformation"
            title="Ce qui change entre le début et la fin"
            lead="La formation ne promet pas une marque « inspirante ». Elle promet une marque décidée, documentée et applicable."
          />
        </Reveal>

        <Reveal delay={0.08} className="mt-11">
          <div className="overflow-hidden rounded-lg border border-ink-200">
            <div className="grid grid-cols-2 border-b border-ink-200 bg-pearl">
              <p className="px-5 py-3.5 font-display text-[12px] font-semibold uppercase tracking-[0.14em] text-ink-500 sm:px-7">
                Avant
              </p>
              <p className="border-l border-ink-200 px-5 py-3.5 font-display text-[12px] font-semibold uppercase tracking-[0.14em] text-teal sm:px-7">
                Après
              </p>
            </div>

            {transformation.map((row) => (
              <div
                key={row.before}
                className="grid grid-cols-2 border-b border-ink-200 last:border-b-0"
              >
                <p className="px-5 py-5 text-[15px] leading-snug text-ink-500 sm:px-7 sm:text-[16px]">
                  {row.before}
                </p>
                <p className="border-l border-ink-200 px-5 py-5 text-[15px] font-medium leading-snug text-ink-900 sm:px-7 sm:text-[16px]">
                  {row.after}
                </p>
              </div>
            ))}
          </div>
        </Reveal>
      </Section>

      {/* --- Pour qui / pas pour qui ------------------------------------- */}
      <Section tone="pearl">
        <div className="grid gap-6 lg:grid-cols-2 lg:gap-8">
          <Reveal>
            <div className="h-full rounded-lg border border-ink-200 bg-white p-7 sm:p-9">
              <Badge tone="teal">Pour toi si</Badge>
              <ul className="mt-6 flex flex-col gap-4">
                {course.forWho.map((item) => (
                  <li key={item} className="flex gap-3.5">
                    <span aria-hidden="true" className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-teal" />
                    <span className="text-[16px] leading-relaxed text-ink-700">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>

          <Reveal delay={0.08}>
            <div className="h-full rounded-lg border border-ink-200 bg-white p-7 sm:p-9">
              <Badge tone="neutral">Pas pour toi si</Badge>
              <ul className="mt-6 flex flex-col gap-4">
                {course.notForWho.map((item) => (
                  <li key={item} className="flex gap-3.5">
                    <span aria-hidden="true" className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-ink-300" />
                    <span className="text-[16px] leading-relaxed text-ink-500">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        </div>
      </Section>

      {/* --- Programme ---------------------------------------------------- */}
      <Section tone="obsidian" id="programme">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <SectionHeading
            tone="dark"
            eyebrow="Le programme"
            title={`${course.modules.length} modules, ${course.totalLessons} leçons`}
            lead="Chaque module installe une couche du système et se termine par un atelier pratique."
          />
          <Link
            href="/formation/programme"
            className="group inline-flex items-center gap-2 font-display text-[15px] font-semibold text-crown"
          >
            Voir le programme détaillé
            <ArrowRight className="transition-transform duration-300 group-hover:translate-x-1" />
          </Link>
        </div>

        <div className="mt-11">
          <ModuleTimeline modules={course.modules} tone="dark" />
        </div>
      </Section>

      {/* --- Formateur ---------------------------------------------------- */}
      <Section tone="white">
        <div className="grid gap-12 lg:grid-cols-[0.85fr_1.15fr] lg:gap-16">
          <Reveal>
            {/* TODO : remplacer par la photo du formateur. */}
            <div className="grid aspect-[4/5] place-items-center rounded-lg border border-ink-200 bg-pearl">
              <div className="text-center">
                <span className="mx-auto grid h-20 w-20 place-items-center rounded-full bg-obsidian font-display text-2xl font-bold text-crown">
                  BO
                </span>
                <p className="mt-4 text-[13px] text-ink-400">
                  Portrait à intégrer
                </p>
              </div>
            </div>
          </Reveal>

          <Reveal delay={0.08}>
            <SectionHeading
              eyebrow="Qui enseigne"
              title="Une méthode issue de la pratique, pas d’un cours théorique"
            />
            <div className="mt-6 flex flex-col gap-5 text-[17px] leading-relaxed text-ink-700">
              <p>
                BrandOS est né d’un constat répété en accompagnement : les
                solopreneurs ne manquent ni de goût ni d’idées. Ils manquent
                d’un cadre de décision — quelque chose qui dise dans quel ordre
                trancher, et à quel moment considérer qu’une étape est finie.
              </p>
              <p>
                La formation reprend exactement ce cadre, celui appliqué aux
                marques présentées dans les études de cas. Rien n’y est
                théorique : chaque leçon débouche sur un livrable qui alimente
                le système Notion.
              </p>
              <p className="text-[15px] text-ink-500">
                {/* TODO : remplacer par la vraie bio du formateur. */}
                Biographie détaillée à compléter avant la mise en ligne.
              </p>
            </div>
          </Reveal>
        </div>
      </Section>

      {/* --- Tarif -------------------------------------------------------- */}
      <Section tone="charcoal">
        <div className="mx-auto max-w-3xl rounded-lg border border-white/12 bg-obsidian p-8 sm:p-12">
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <Eyebrow tone="crown">Tarif unique</Eyebrow>
              <h2 className="mt-3 text-3xl text-white sm:text-4xl">
                {course.name}
              </h2>
            </div>
            <p className="font-display">
              <span className="text-4xl font-bold tracking-[-0.03em] text-white">
                {formatPrice(course.price)}
              </span>
              {course.compareAtPrice && (
                <span className="ml-2 text-lg text-white/40 line-through">
                  {formatPrice(course.compareAtPrice)}
                </span>
              )}
            </p>
          </div>

          <ul className="mt-8 grid gap-3.5 sm:grid-cols-2">
            {course.includes.map((item) => (
              <li key={item} className="flex gap-3">
                <span
                  aria-hidden="true"
                  className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-crown text-obsidian"
                >
                  <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M2.5 6.5 L5 9 L9.5 3.5" />
                  </svg>
                </span>
                <span className="text-[15px] leading-relaxed text-dark-muted">{item}</span>
              </li>
            ))}
          </ul>

          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <ButtonLink href="/tarifs" size="lg">
              Rejoindre la formation
              <ArrowRight />
            </ButtonLink>
            <ButtonLink href="/espace-membre" variant="secondary-dark" size="lg">
              Voir l’espace membre
            </ButtonLink>
          </div>
        </div>
      </Section>

      {/* --- Témoignages + FAQ -------------------------------------------- */}
      <Section tone="white">
        <div className="mx-auto max-w-3xl">
          <TestimonialCarousel items={testimonials.slice(0, 4)} />
        </div>
      </Section>

      <Section tone="pearl">
        <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
          <SectionHeading
            eyebrow="Questions fréquentes"
            title="Sur la formation"
            lead="Les autres questions — produits, facturation, technique — sont dans la FAQ complète."
          />
          <div>
            <FaqBlock items={formationFaq} idPrefix="formation-faq" />
            <Link
              href="/faq"
              className="group mt-6 inline-flex items-center gap-2 font-display text-[15px] font-semibold text-teal hover:text-teal-hover"
            >
              Voir toutes les questions
              <ArrowRight className="transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
          </div>
        </div>
      </Section>
    </PageShell>
  );
}
