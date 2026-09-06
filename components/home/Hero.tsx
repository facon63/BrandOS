"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/Container";
import { Magnetic } from "@/components/motion/Magnetic";
import { SplitReveal } from "@/components/motion/SplitReveal";
import { DashboardMock } from "@/components/ui/MockShot";

/**
 * Hero d'accueil. Le plumage vit derrière (PeacockField, au niveau de la page)
 * — ici on ne pose que le texte et l'aperçu produit, sur fond transparent.
 */
export function Hero() {
  const reduced = useReducedMotion();
  const fade = (delay: number) =>
    reduced
      ? {}
      : {
          initial: { opacity: 0, y: 16 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.8, delay, ease: [0.16, 1, 0.3, 1] as const },
        };

  return (
    <section className="relative flex min-h-[100svh] items-center pt-[72px]">
      <Container className="relative py-20 sm:py-24">
        <div className="grid items-center gap-16 lg:grid-cols-[1.08fr_0.92fr]">
          <div>
            <motion.p
              {...fade(0)}
              className="inline-flex items-center gap-2.5 rounded-full border border-white/15 bg-white/[0.04] px-4 py-1.5 font-display text-[12px] font-semibold uppercase tracking-[0.16em] text-crown backdrop-blur-sm"
            >
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-crown opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-crown" />
              </span>
              Système de marque pour solopreneurs
            </motion.p>

            <SplitReveal
              delay={0.1}
              className="mt-7 font-display text-[2.7rem] font-bold leading-[0.98] tracking-[-0.035em] text-white sm:text-6xl lg:text-[4.4rem]"
              lines={[
                "Le système",
                "d’exploitation",
                <>
                  de ta{" "}
                  <span className="relative inline-block">
                    <span className="relative z-10">marque</span>
                    <motion.span
                      aria-hidden="true"
                      className="absolute inset-x-0 bottom-[-0.06em] -z-0 h-[0.1em] origin-left rounded-full bg-crown"
                      initial={reduced ? undefined : { scaleX: 0 }}
                      animate={{ scaleX: 1 }}
                      transition={{ duration: 0.7, delay: 0.85, ease: [0.16, 1, 0.3, 1] }}
                    />
                  </span>
                </>,
              ]}
            />

            <motion.p
              {...fade(0.5)}
              className="mt-8 max-w-xl text-lg leading-relaxed text-white/60 sm:text-xl"
            >
              Positionnement, identité visuelle, voix, organisation : BrandOS
              structure tout ce qu’il te faut pour lancer une marque qui a de
              l’allure — sans agence, sans flou.
            </motion.p>

            <motion.div {...fade(0.62)} className="mt-10 flex flex-col gap-3 sm:flex-row">
              <Magnetic>
                <ButtonLink href="/produits" size="lg">
                  Découvrir BrandOS
                  <ArrowRight />
                </ButtonLink>
              </Magnetic>
              <ButtonLink href="/etudes-de-cas" variant="secondary-dark" size="lg">
                Voir une étude de cas
              </ButtonLink>
            </motion.div>

            <motion.p {...fade(0.74)} className="mt-7 text-[14px] text-white/35">
              Accès à vie · Mises à jour incluses · Garantie 30 jours
            </motion.p>
          </div>

          <motion.div
            {...(reduced
              ? {}
              : {
                  initial: { opacity: 0, y: 40, rotateX: 12 },
                  animate: { opacity: 1, y: 0, rotateX: 0 },
                  transition: { duration: 1.1, delay: 0.35, ease: [0.16, 1, 0.3, 1] as const },
                })}
            style={{ transformPerspective: 1200 }}
            className="relative"
          >
            <div className="rounded-xl border border-white/12 bg-charcoal/70 p-4 shadow-[0_40px_120px_-20px_rgb(0_0_0/0.8)] backdrop-blur-md sm:p-5">
              <div className="mb-4 flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-white/20" />
                <span className="h-2 w-2 rounded-full bg-white/20" />
                <span className="h-2 w-2 rounded-full bg-white/20" />
                <span className="ml-2 font-display text-[11px] font-semibold uppercase tracking-[0.16em] text-white/35">
                  BrandOS · Dashboard
                </span>
              </div>
              <div className="rounded-lg bg-white p-4">
                <DashboardMock animated />
              </div>
            </div>
            <p className="mt-4 text-center text-[12px] text-white/25">
              Aperçu du dashboard de suivi — données de démonstration
            </p>
          </motion.div>
        </div>
      </Container>

      <ScrollCue />
    </section>
  );
}

function ScrollCue() {
  const reduced = useReducedMotion();
  return (
    <motion.div
      aria-hidden="true"
      className="absolute inset-x-0 bottom-8 flex justify-center"
      initial={reduced ? undefined : { opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 1.4, duration: 0.8 }}
    >
      <span className="flex h-11 w-6 items-start justify-center rounded-full border border-white/20 p-1.5">
        <motion.span
          className="h-2 w-1 rounded-full bg-crown"
          animate={reduced ? undefined : { y: [0, 12, 0], opacity: [1, 0.3, 1] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
        />
      </span>
    </motion.div>
  );
}
