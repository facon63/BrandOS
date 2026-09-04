import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { PageHero } from "@/components/layout/PageHero";
import { Section } from "@/components/ui/Section";
import { ProductGrid } from "@/components/products/ProductGrid";
import { CtaBanner } from "@/components/marketing/CtaBanner";
import { products } from "@/data/products";

export const metadata: Metadata = {
  title: "Produits digitaux",
  description:
    "Le Kit BrandOS & Roadmap, la checklist Launch-Ready, la bibliothèque de prompts IA : les briques du système, à installer dans ton espace de travail.",
};

export default function ProduitsPage() {
  return (
    <PageShell headerTone="dark">
      <PageHero
        eyebrow="Module 01 — Produits digitaux"
        title="Les briques du système, prêtes à installer"
        lead="Des outils qu’on utilise soi-même, pas des templates achetés en gros. Chacun s’installe en quelques minutes et se connecte aux autres."
        crumbs={[{ href: "/", label: "Accueil" }, { label: "Produits" }]}
      />

      <Section tone="white">
        <ProductGrid products={products} />
      </Section>

      <Section tone="pearl" spacing="tight">
        <div className="grid gap-8 sm:grid-cols-3">
          {[
            {
              title: "Accès à vie",
              body: "Tu achètes une fois. L’accès ne se renouvelle pas et ne se résilie pas.",
            },
            {
              title: "Mises à jour incluses",
              body: "Chaque nouvelle version arrive dans ton espace, sans surcoût.",
            },
            {
              title: "Garantie 30 jours",
              body: "Sur la formation et les bundles, remboursement sans justification.",
            },
          ].map((item) => (
            <div key={item.title}>
              <h2 className="font-display text-[17px] font-semibold tracking-[-0.015em] text-ink-900">
                {item.title}
              </h2>
              <p className="mt-2 text-[15px] leading-relaxed text-ink-600">{item.body}</p>
            </div>
          ))}
        </div>
      </Section>

      <CtaBanner
        title="Pas sûr par où commencer ?"
        lead="Si ta marque n’a jamais été tranchée, commence par le Kit BrandOS & Roadmap. Si seul l’habillage cloche, le module Identité visuelle suffit."
        primary={{ href: "/produits/kit-brandos-roadmap", label: "Voir le Kit BrandOS" }}
        secondary={{ href: "/contact", label: "Nous demander conseil" }}
      />
    </PageShell>
  );
}
