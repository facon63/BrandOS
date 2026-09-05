import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { PageHero } from "@/components/layout/PageHero";
import { Section } from "@/components/ui/Section";
import { Eyebrow } from "@/components/ui/Badge";
import { AuthPanel } from "@/components/account/AuthPanel";

export const metadata: Metadata = {
  title: "Mon compte",
  robots: { index: false },
};

const perks = [
  {
    title: "Tes accès au même endroit",
    body: "Kit Notion, checklists, formation : tout ce que tu as acheté reste accessible depuis ton compte, à vie.",
  },
  {
    title: "Ta progression conservée",
    body: "L’espace membre retient où tu t’es arrêté, leçon par leçon. Tu peux reprendre six mois plus tard.",
  },
  {
    title: "Tes factures",
    body: "Chaque achat génère une facture PDF, disponible en téléchargement à tout moment.",
  },
];

export default function ComptePage() {
  return (
    <PageShell headerTone="dark">
      <PageHero
        eyebrow="Mon compte"
        title="Connexion à ton espace"
        lead="Un seul compte pour tes produits, ta formation et tes factures."
        crumbs={[{ href: "/", label: "Accueil" }, { label: "Compte" }]}
      >
        <p className="rounded-md border border-crown/30 bg-crown/10 px-4 py-3 text-[14px] text-white">
          <span className="font-semibold text-crown">Démonstration —</span>{" "}
          l’authentification n’est pas branchée. Aucun identifiant n’est vérifié
          ni enregistré.
        </p>
      </PageHero>

      <Section tone="pearl">
        <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16">
          <div>
            <Eyebrow>Ce que ton compte contient</Eyebrow>
            <h2 className="mt-3 text-3xl text-ink-900 sm:text-4xl">
              Tes accès, ta progression, tes factures
            </h2>

            <div className="mt-9 flex flex-col gap-7">
              {perks.map((perk, i) => (
                <div key={perk.title} className="flex gap-5">
                  <span className="font-display text-[13px] font-bold text-crown">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <h3 className="font-display text-[17px] font-semibold tracking-[-0.015em] text-ink-900">
                      {perk.title}
                    </h3>
                    <p className="mt-1.5 text-[15px] leading-relaxed text-ink-600">
                      {perk.body}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <AuthPanel />
        </div>
      </Section>
    </PageShell>
  );
}
