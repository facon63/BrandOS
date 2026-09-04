import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { PageHero } from "@/components/layout/PageHero";
import { Section } from "@/components/ui/Section";
import { Badge, Eyebrow } from "@/components/ui/Badge";
import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { Reveal } from "@/components/ui/Reveal";
import { FaqBlock } from "@/components/marketing/FaqBlock";
import { getProduct } from "@/data/products";
import { course } from "@/data/courses";
import { faq } from "@/data/faq";
import { cx, formatPrice } from "@/lib/format";

export const metadata: Metadata = {
  title: "Tarifs",
  description:
    "Trois façons d’installer BrandOS : le kit seul, la formation complète, ou le pack qui réunit les deux. Comparatif détaillé.",
};

const kit = getProduct("kit-brandos-roadmap")!;
const pack = getProduct("pack-lancement-complet")!;

const offers = [
  {
    name: kit.name,
    price: kit.price,
    compareAt: kit.compareAtPrice,
    pitch: "Pour installer la structure et avancer en autonomie.",
    href: `/produits/${kit.slug}`,
    cta: "Prendre le kit",
    featured: false,
  },
  {
    name: pack.name,
    price: pack.price,
    compareAt: pack.compareAtPrice,
    pitch: "Le système complet et la méthode qui va avec. Le meilleur rapport.",
    href: `/produits/${pack.slug}`,
    cta: "Prendre le pack",
    featured: true,
  },
  {
    name: course.name,
    price: course.price,
    compareAt: course.compareAtPrice,
    pitch: "Pour comprendre chaque décision, avec le kit inclus.",
    href: "/formation",
    cta: "Rejoindre la formation",
    featured: false,
  },
];

/** Matrice comparative : `true` inclus, `false` non inclus, string = précision. */
const matrix: { label: string; values: [boolean | string, boolean | string, boolean | string] }[] = [
  { label: "6 bases de données Notion", values: [true, true, true] },
  { label: "Dashboard de suivi", values: [true, true, true] },
  { label: "Checklist Launch-Ready (24 actions)", values: [true, true, true] },
  { label: "Bibliothèque de prompts IA", values: ["12 prompts", "48 prompts", "48 prompts"] },
  { label: "Système d’identité visuelle", values: [false, true, false] },
  { label: "Formation vidéo (5 modules)", values: [false, true, true] },
  { label: "Espace membre et suivi de progression", values: [false, true, true] },
  { label: "Ressources téléchargeables par module", values: [false, true, true] },
  { label: "Mises à jour à vie", values: [true, true, true] },
  { label: "Garantie 30 jours", values: [false, true, true] },
];

export default function TarifsPage() {
  const billingFaq = faq.filter((f) => f.category === "Facturation");

  return (
    <PageShell headerTone="dark">
      <PageHero
        eyebrow="Tarifs"
        title="Trois façons d’installer BrandOS"
        lead="Un achat unique dans les trois cas : pas d’abonnement, pas de reconduction. Tu peux commencer par le kit et compléter plus tard, la différence est déduite."
        crumbs={[{ href: "/", label: "Accueil" }, { label: "Tarifs" }]}
      />

      <Section tone="white">
        <div className="grid gap-5 lg:grid-cols-3">
          {offers.map((offer, i) => (
            <Reveal key={offer.name} delay={i * 0.06} className="h-full">
              <div
                className={cx(
                  "flex h-full flex-col rounded-lg border p-7 sm:p-8",
                  offer.featured
                    ? "on-dark border-obsidian bg-obsidian text-white"
                    : "border-ink-200 bg-white",
                )}
              >
                {offer.featured && <Badge tone="crown">Recommandé</Badge>}

                <h2
                  className={cx(
                    "font-display text-2xl font-bold tracking-[-0.025em]",
                    offer.featured ? "mt-5 text-white" : "text-ink-900",
                  )}
                >
                  {offer.name}
                </h2>

                <p
                  className={cx(
                    "mt-2.5 text-[15px] leading-relaxed",
                    offer.featured ? "text-dark-muted" : "text-ink-600",
                  )}
                >
                  {offer.pitch}
                </p>

                <p className="mt-7 flex items-baseline gap-2.5">
                  <span
                    className={cx(
                      "font-display text-4xl font-bold tracking-[-0.03em]",
                      offer.featured ? "text-white" : "text-ink-900",
                    )}
                  >
                    {formatPrice(offer.price)}
                  </span>
                  {offer.compareAt && (
                    <span
                      className={cx(
                        "font-display text-[16px] line-through",
                        offer.featured ? "text-white/40" : "text-ink-400",
                      )}
                    >
                      {formatPrice(offer.compareAt)}
                    </span>
                  )}
                </p>
                <p
                  className={cx(
                    "mt-1 text-[13px]",
                    offer.featured ? "text-white/40" : "text-ink-400",
                  )}
                >
                  Paiement unique · TVA incluse
                </p>

                <div className="mt-auto pt-8">
                  <ButtonLink
                    href={offer.href}
                    size="lg"
                    variant={offer.featured ? "primary" : "secondary"}
                    className="w-full"
                  >
                    {offer.cta}
                  </ButtonLink>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </Section>

      {/* --- Comparatif détaillé ------------------------------------------ */}
      <Section tone="pearl">
        <Eyebrow>Comparatif</Eyebrow>
        <h2 className="mt-3 text-3xl text-ink-900 sm:text-4xl">
          Ce que contient chaque offre
        </h2>

        {/* Le tableau défile horizontalement sur mobile plutôt que d’écraser
            la page : la largeur minimale garde les colonnes lisibles. */}
        <div className="mt-10 overflow-x-auto rounded-lg border border-ink-200 bg-white">
          <table className="w-full min-w-[42rem] border-collapse text-left">
            <caption className="sr-only">
              Comparatif du contenu des trois offres BrandOS
            </caption>
            <thead>
              <tr className="border-b border-ink-200">
                <th scope="col" className="px-5 py-4 font-display text-[13px] font-semibold uppercase tracking-[0.1em] text-ink-400 sm:px-6">
                  Contenu
                </th>
                {offers.map((o) => (
                  <th
                    key={o.name}
                    scope="col"
                    className={cx(
                      "px-5 py-4 font-display text-[14px] font-semibold sm:px-6",
                      o.featured ? "text-ink-900" : "text-ink-600",
                    )}
                  >
                    {o.name}
                    {o.featured && (
                      <span className="ml-2 rounded-full bg-crown px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-obsidian">
                        Recommandé
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.map((row) => (
                <tr key={row.label} className="border-b border-ink-100 last:border-b-0">
                  <th
                    scope="row"
                    className="px-5 py-4 text-[15px] font-normal text-ink-800 sm:px-6"
                  >
                    {row.label}
                  </th>
                  {row.values.map((value, i) => (
                    <td key={i} className="px-5 py-4 sm:px-6">
                      <Cell value={value} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-5 text-[14px] text-ink-500">
          Paiement en trois fois sans frais prévu au lancement sur la formation et
          les bundles.
        </p>
      </Section>

      <Section tone="white">
        <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
          <div>
            <Eyebrow>Facturation</Eyebrow>
            <h2 className="mt-3 text-3xl text-ink-900 sm:text-4xl">
              Paiement, facture, remboursement
            </h2>
            <ButtonLink href="/contact" variant="secondary" className="mt-7">
              Une question sur une offre
              <ArrowRight />
            </ButtonLink>
          </div>
          <FaqBlock items={billingFaq} idPrefix="tarifs-faq" />
        </div>
      </Section>
    </PageShell>
  );
}

function Cell({ value }: { value: boolean | string }) {
  if (typeof value === "string") {
    return <span className="text-[14px] font-medium text-ink-800">{value}</span>;
  }

  if (value) {
    return (
      <>
        <span
          aria-hidden="true"
          className="grid h-5 w-5 place-items-center rounded-full bg-crown text-obsidian"
        >
          <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2.5 6.5 L5 9 L9.5 3.5" />
          </svg>
        </span>
        <span className="sr-only">Inclus</span>
      </>
    );
  }

  return (
    <>
      <span aria-hidden="true" className="block h-px w-4 rounded bg-ink-300" />
      <span className="sr-only">Non inclus</span>
    </>
  );
}
