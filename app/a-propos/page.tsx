import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { PageHero } from "@/components/layout/PageHero";
import { Section } from "@/components/ui/Section";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";
import { Eyebrow } from "@/components/ui/Badge";
import { FeatherDivider } from "@/components/brand/FeatherDivider";
import { PeacockMarkStatic } from "@/components/brand/PeacockMark";
import { CtaBanner } from "@/components/marketing/CtaBanner";

export const metadata: Metadata = {
  title: "À propos",
  description:
    "Pourquoi BrandOS existe : la rigueur d’un système d’exploitation appliquée à la marque personnelle, sans agence et sans flou créatif.",
};

const values = [
  {
    title: "Trancher plutôt qu’inspirer",
    body: "Une planche d’inspiration ne décide rien. Un système, si. Chaque étape de BrandOS se termine par une décision écrite et datée.",
  },
  {
    title: "Un critère de fin partout",
    body: "« Travailler mon positionnement » n’est pas une tâche. « Une promesse de moins de 20 mots validée par trois personnes de ma cible » en est une.",
  },
  {
    title: "Réduire avant d’ajouter",
    body: "La plupart des marques n’ont pas besoin de plus de couleurs, de polices ou de formats. Elles ont besoin d’en retirer.",
  },
  {
    title: "Le fond avant la forme",
    body: "On ne choisit pas une typographie tant qu’on ne sait pas à qui l’on parle. L’ordre des décisions n’est pas négociable.",
  },
];

const manifesto = [
  {
    title: "La structure invisible",
    body: "Un système d’exploitation ne se voit pas. On ne l’admire pas : on s’en sert. C’est ce que BrandOS est pour une marque — les bases de données, les règles, les rituels qui tournent en arrière-plan et rendent tout le reste possible.",
  },
  {
    title: "L’expression visible",
    body: "Et puis il y a ce qu’on montre. Le paon qui déploie ses plumes, la marque qui s’affiche enfin sans s’excuser. Ce moment n’arrive jamais par hasard : il arrive quand la structure derrière est assez solide pour le porter.",
  },
  {
    title: "La couronne",
    body: "Le positionnement premium ne se décrète pas dans un logo. Il se gagne en refusant : refuser des clients, des formats, des couleurs, des promesses. C’est ce que la couronne signifie ici — la maîtrise, pas l’ornement.",
  },
];

export default function AProposPage() {
  return (
    <PageShell headerTone="dark">
      <PageHero
        eyebrow="Le manifeste"
        title="Ta marque a déjà des choses à montrer. Il lui manque la structure pour les déployer."
        lead="BrandOS est né d’une frustration simple : les solopreneurs les plus compétents ont souvent les marques les plus floues. Pas par manque de goût — par absence de cadre de décision."
        crumbs={[{ href: "/", label: "Accueil" }, { label: "À propos" }]}
      />

      <Section tone="white">
        <div className="grid gap-14 lg:grid-cols-[0.85fr_1.15fr] lg:gap-16">
          <Reveal>
            <PeacockMarkStatic className="h-32 w-auto text-obsidian" />
            <FeatherDivider className="mt-8 max-w-[16rem]" />
          </Reveal>

          <Reveal delay={0.08}>
            <SectionHeading
              eyebrow="Le principe"
              title="Un système d’exploitation, pas une planche d’inspiration"
              lead="Deux tensions traversent tout ce qu’on construit : la précision d’un outil technique, et le raffinement d’une identité qui a de l’allure. L’une sans l’autre ne tient pas."
            />

            <div className="mt-10 flex flex-col gap-9">
              {manifesto.map((block) => (
                <div key={block.title} className="border-l-2 border-crown pl-6">
                  <h3 className="font-display text-xl font-bold tracking-[-0.02em] text-ink-900">
                    {block.title}
                  </h3>
                  <p className="mt-2.5 text-[17px] leading-relaxed text-ink-700">
                    {block.body}
                  </p>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </Section>

      <Section tone="obsidian">
        <Reveal>
          <SectionHeading
            tone="dark"
            align="center"
            eyebrow="Nos valeurs"
            title="Quatre principes, appliqués sans exception"
            lead="Ils décident du contenu des produits, de l’ordre des modules, et de ce qu’on refuse d’ajouter."
          />
        </Reveal>

        <div className="mt-12 grid gap-5 sm:grid-cols-2">
          {values.map((v, i) => (
            <Reveal key={v.title} delay={i * 0.06}>
              <div className="h-full rounded-lg border border-white/12 bg-charcoal p-7">
                <span className="font-display text-[13px] font-bold text-crown">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h3 className="mt-3 font-display text-xl font-bold tracking-[-0.02em] text-white">
                  {v.title}
                </h3>
                <p className="mt-3 text-[15px] leading-relaxed text-dark-muted">
                  {v.body}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </Section>

      <Section tone="pearl">
        <div className="mx-auto max-w-3xl">
          <Eyebrow>L’histoire</Eyebrow>
          <h2 className="mt-3 text-3xl text-ink-900 sm:text-4xl">
            D’un tableur bricolé à un système
          </h2>

          <div className="mt-7 flex flex-col gap-5 text-[17px] leading-relaxed text-ink-700">
            <p>
              BrandOS a commencé comme un tableur privé : une liste de questions
              posées systématiquement en début d’accompagnement, parce que les
              mêmes blocages revenaient chez presque tout le monde.
            </p>
            <p>
              Le tableur est devenu une base Notion, puis six bases reliées, puis
              une roadmap, puis une formation pour expliquer les décisions
              derrière la structure. À chaque étape, une seule règle : si une
              partie ne servait pas à décider quelque chose, elle sautait.
            </p>
            <p className="rounded-lg border border-dashed border-ink-300 p-5 text-[15px] text-ink-500">
              {/* TODO : remplacer par l’histoire réelle du fondateur. */}
              Section à compléter avec le parcours du fondateur, les dates clés
              et les chiffres réels avant la mise en ligne.
            </p>
          </div>
        </div>
      </Section>

      <CtaBanner
        title="Le manifeste, c’est bien. Le système, c’est mieux."
        lead="Tout ce qui est écrit sur cette page est déjà traduit en bases de données, en checklists et en modules vidéo."
        primary={{ href: "/produits", label: "Voir les produits" }}
        secondary={{ href: "/formation", label: "Découvrir la formation" }}
      />
    </PageShell>
  );
}
