import type { Metadata } from "next";
import Link from "next/link";
import { PageShell } from "@/components/layout/PageShell";
import { PageHero } from "@/components/layout/PageHero";
import { Section } from "@/components/ui/Section";
import { Eyebrow } from "@/components/ui/Badge";
import { ContactForm } from "@/components/marketing/ContactForm";
import { site, socials } from "@/data/site";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Une question sur les produits, la formation ou une licence pro ? Écris-nous, on répond en général sous 24 h ouvrées.",
};

export default function ContactPage() {
  return (
    <PageShell headerTone="dark">
      <PageHero
        eyebrow="Contact"
        title="Dis-nous où tu en es"
        lead="Choix de l’offre, licence pro, question technique : plus ton message est précis, plus la réponse est utile."
        crumbs={[{ href: "/", label: "Accueil" }, { label: "Contact" }]}
      />

      <Section tone="white">
        <div className="grid gap-14 lg:grid-cols-[1.15fr_0.85fr] lg:gap-16">
          <ContactForm />

          <aside className="flex flex-col gap-8">
            <div className="rounded-lg border border-ink-200 bg-pearl/60 p-7">
              <Eyebrow>En direct</Eyebrow>
              <p className="mt-3 text-[15px] leading-relaxed text-ink-700">
                Pour une question courte, l’e-mail reste le plus rapide.
              </p>
              <a
                href={`mailto:${site.email}`}
                className="mt-3 inline-block font-display text-[16px] font-semibold text-teal hover:text-teal-hover"
              >
                {site.email}
              </a>
            </div>

            <div className="rounded-lg border border-ink-200 p-7">
              <Eyebrow>Avant d’écrire</Eyebrow>
              <p className="mt-3 text-[15px] leading-relaxed text-ink-700">
                Les questions sur le contenu des offres, la facturation et les
                remboursements sont déjà traitées dans la FAQ.
              </p>
              <Link
                href="/faq"
                className="mt-3 inline-block font-display text-[15px] font-semibold text-teal hover:text-teal-hover"
              >
                Consulter la FAQ
              </Link>
            </div>

            <div className="rounded-lg border border-ink-200 p-7">
              <Eyebrow>Ailleurs</Eyebrow>
              <ul className="mt-4 flex flex-col gap-2.5">
                {socials.map((s) => (
                  /* Placeholders : remplacer par les vraies URLs. */
                  <li key={s.label}>
                    <a
                      href={s.href}
                      className="text-[15px] text-ink-700 transition-colors hover:text-ink-900"
                    >
                      {s.label} <span className="text-ink-400">{s.handle}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>
      </Section>
    </PageShell>
  );
}
