import Link from "next/link";
import { PageShell } from "@/components/layout/PageShell";
import { Hero } from "@/components/home/Hero";
import { TrustBar } from "@/components/home/TrustBar";
import { ProblemSection } from "@/components/home/ProblemSection";
import { PillarsSection } from "@/components/home/PillarsSection";
import { ProductPreview } from "@/components/home/ProductPreview";
import { FeaturedCase } from "@/components/home/FeaturedCase";
import { CtaBanner } from "@/components/marketing/CtaBanner";
import { FaqBlock } from "@/components/marketing/FaqBlock";
import { TestimonialCarousel } from "@/components/marketing/TestimonialCarousel";
import { Section } from "@/components/ui/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";
import { ArrowRight } from "@/components/ui/Button";
import { testimonials } from "@/data/testimonials";
import { homeFaq } from "@/data/faq";

export default function HomePage() {
  return (
    <PageShell headerTone="dark">
      <Hero />
      <TrustBar />
      <ProblemSection />
      <PillarsSection />
      <ProductPreview />
      <FeaturedCase />

      <Section tone="charcoal" id="temoignages">
        <div className="grid gap-12 lg:grid-cols-[0.85fr_1.15fr] lg:gap-16">
          <Reveal>
            <SectionHeading
              tone="dark"
              eyebrow="Ils l’ont installé"
              title="Des marques qui ont arrêté de tout recommencer"
              lead="Ce qui revient le plus souvent : « le problème n’était pas le logo »."
            />
          </Reveal>
          <Reveal delay={0.08}>
            <TestimonialCarousel items={testimonials} tone="dark" />
          </Reveal>
        </div>
      </Section>

      <Section tone="white" id="faq">
        <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
          <Reveal>
            <SectionHeading
              eyebrow="Questions fréquentes"
              title="Ce qu’on nous demande avant d’acheter"
              lead="Les quatre questions qui reviennent le plus. Le reste est dans la FAQ complète."
            />
            <Link
              href="/faq"
              className="group mt-6 inline-flex items-center gap-2 font-display text-[15px] font-semibold text-teal transition-colors hover:text-teal-hover"
            >
              Voir toutes les questions
              <ArrowRight className="transition-transform duration-300 group-hover:translate-x-1" />
            </Link>
          </Reveal>
          <Reveal delay={0.08}>
            <FaqBlock items={homeFaq} idPrefix="home-faq" />
          </Reveal>
        </div>
      </Section>

      <CtaBanner />
    </PageShell>
  );
}
