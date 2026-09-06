"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Container } from "@/components/ui/Container";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";

const symptoms = [
  {
    title: "Trois logos en circulation",
    body: "Un sur le site, un autre sur Instagram, un troisième sur les factures. Personne ne sait lequel est le bon — toi non plus.",
  },
  {
    title: "Une bio interchangeable",
    body: "« Passionné par mon métier, j’accompagne mes clients avec bienveillance. » Quatre cents personnes écrivent exactement la même phrase.",
  },
  {
    title: "Un site jamais fini",
    body: "Commencé deux fois, refondu une fois et demie. Toujours bloqué sur la page d’accueil, parce que la promesse n’a jamais été tranchée.",
  },
  {
    title: "Des décisions renégociées",
    body: "Chaque publication rouvre le débat de la couleur, de la police, du ton. Rien n’est écrit, donc tout se rediscute.",
  },
];

/**
 * Le diagnostic. Les cards arrivent volontairement de travers puis se
 * redressent : le désordre du plumage derrière se rejoue dans la mise en page.
 */
export function ProblemSection() {
  const reduced = useReducedMotion();

  return (
    <section id="probleme" className="relative py-24 sm:py-32">
      <Container>
        <div className="grid gap-14 lg:grid-cols-[0.95fr_1.05fr] lg:gap-20">
          <Reveal>
            <SectionHeading
              tone="dark"
              eyebrow="Le diagnostic"
              title={
                <>
                  Tu es doué dans ton métier.
                  <br />
                  <span className="text-white/35">
                    Ta marque, elle, part dans tous les sens.
                  </span>
                </>
              }
              lead="Ce n’est presque jamais un problème de goût. C’est un problème de décisions jamais prises — et donc rejouées chaque semaine."
            />

            <div className="mt-9 rounded-lg border-l-2 border-crown bg-white/[0.03] p-6 backdrop-blur-sm">
              <p className="font-display text-lg font-semibold leading-snug tracking-[-0.015em] text-white">
                Le vrai coût n’est pas esthétique.
              </p>
              <p className="mt-2 text-[15px] leading-relaxed text-white/55">
                C’est le temps perdu à refaire, l’énergie dépensée à hésiter, et
                les clients qui ne savent pas te recommander parce qu’ils
                n’arrivent pas à résumer ce que tu fais.
              </p>
            </div>
          </Reveal>

          <div className="grid gap-4 sm:grid-cols-2">
            {symptoms.map((s, i) => (
              <motion.div
                key={s.title}
                initial={
                  reduced
                    ? undefined
                    : { opacity: 0, y: 30, rotate: i % 2 === 0 ? -2.5 : 2.5 }
                }
                whileInView={{ opacity: 1, y: 0, rotate: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{
                  duration: 0.7,
                  delay: i * 0.08,
                  ease: [0.16, 1, 0.3, 1],
                }}
                className="group h-full rounded-lg border border-white/10 bg-charcoal/50 p-6 backdrop-blur-sm transition-colors duration-300 hover:border-crown/40 hover:bg-charcoal/70"
              >
                <span className="font-display text-[13px] font-bold text-crown">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h3 className="mt-2.5 font-display text-lg font-semibold tracking-[-0.015em] text-white">
                  {s.title}
                </h3>
                <p className="mt-2 text-[15px] leading-relaxed text-white/50">
                  {s.body}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
}
