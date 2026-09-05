import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { PageHero } from "@/components/layout/PageHero";
import { Section } from "@/components/ui/Section";
import { FaqCategories } from "@/components/marketing/FaqCategories";
import { CtaBanner } from "@/components/marketing/CtaBanner";
import { faq, faqCategories } from "@/data/faq";

export const metadata: Metadata = {
  title: "FAQ",
  description:
    "Produits, formation, facturation, technique : les réponses aux questions les plus fréquentes sur BrandOS.",
};

export default function FaqPage() {
  return (
    <PageShell headerTone="dark">
      <PageHero
        eyebrow="FAQ"
        title="Les questions qu’on nous pose vraiment"
        lead="Classées par sujet. Si la tienne n’y est pas, écris-nous : on répond en général sous 24 h ouvrées."
        crumbs={[{ href: "/", label: "Accueil" }, { label: "FAQ" }]}
      />

      <Section tone="white">
        <FaqCategories items={faq} categories={faqCategories} />
      </Section>

      <CtaBanner
        title="Ta question n’est pas là ?"
        lead="Écris-nous en deux lignes. Les réponses utiles finissent souvent par rejoindre cette page."
        primary={{ href: "/contact", label: "Poser une question" }}
        secondary={{ href: "/produits", label: "Voir les produits" }}
      />
    </PageShell>
  );
}
