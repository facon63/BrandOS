import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { PageHero } from "@/components/layout/PageHero";
import { Section } from "@/components/ui/Section";
import { CartSummary } from "@/components/cart/CartSummary";

export const metadata: Metadata = {
  title: "Panier",
  robots: { index: false },
};

export default function PanierPage() {
  return (
    <PageShell headerTone="dark">
      <PageHero
        eyebrow="Panier"
        title="Ta sélection"
        lead="Produits numériques : accès immédiat après l’achat, mises à jour incluses, aucune reconduction."
        crumbs={[{ href: "/", label: "Accueil" }, { label: "Panier" }]}
      >
        <p className="rounded-md border border-crown/30 bg-crown/10 px-4 py-3 text-[14px] text-white">
          <span className="font-semibold text-crown">Démonstration —</span> le
          tunnel de paiement n’est pas encore branché. Le contenu du panier est
          fictif.
        </p>
      </PageHero>

      <Section tone="white">
        <CartSummary />
      </Section>
    </PageShell>
  );
}
