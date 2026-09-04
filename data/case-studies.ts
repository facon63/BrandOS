import type { CaseStudy } from "@/lib/types";

/* ============================================================================
   Études de cas — DONNÉES DE DÉMONSTRATION.
   Clients et chiffres fictifs, clairement à remplacer par de vrais cas
   documentés (avec accord écrit du client) avant mise en ligne.
   Les visuels avant/après sont générés à partir des palettes ci-dessous :
   TODO (phase 2) — remplacer par de vraies captures d’écran.
   ========================================================================= */

export const caseStudies: CaseStudy[] = [
  {
    slug: "atelier-mora",
    client: "Atelier Mora",
    sector: "Artisanat & design",
    headline: "D’un compte Instagram joli à une marque qu’on recommande",
    excerpt:
      "Une céramiste dont le travail était remarquable et la marque illisible. En six semaines, un positionnement, une identité applicable et un premier catalogue.",
    keyMetric: {
      value: "×3",
      label: "demandes de devis qualifiées",
      detail: "sur les 90 jours suivant le lancement",
    },
    featured: true,
    context: [
      "Atelier Mora vendait de la céramique depuis quatre ans, presque exclusivement en salon. Le travail était reconnu, les prix justes, et pourtant chaque nouveau contact repartait de zéro : personne ne savait résumer ce que faisait l’atelier.",
      "Trois logos coexistaient selon les supports. La bio Instagram parlait de « pièces uniques faites main » — comme quatre cents autres comptes. Le site, commencé deux fois, n’avait jamais dépassé la page d’accueil.",
      "Le problème n’était pas esthétique. C’était un problème de décision : rien n’avait jamais été tranché, donc tout était renégocié à chaque publication.",
    ],
    method: [
      {
        step: "01",
        title: "Trancher le positionnement",
        body: "Deux séances pour choisir un terrain : la céramique de table pour restaurants indépendants, pas la pièce décorative. Ce refus a rendu toutes les décisions suivantes évidentes.",
      },
      {
        step: "02",
        title: "Réduire l’identité",
        body: "De douze couleurs héritées de quatre ans d’essais à cinq, testées en contraste sur photo, packaging et facture. Une seule typographie, deux graisses.",
      },
      {
        step: "03",
        title: "Documenter la voix",
        body: "Un guide de deux pages : on parle matière et usage, jamais « passion » ni « authenticité ». Toutes les fiches produit ont été réécrites à partir de là.",
      },
      {
        step: "04",
        title: "Déployer avec la Roadmap",
        body: "Les 24 actions de la checklist Launch-Ready, étalées sur six semaines. Site, catalogue PDF et refonte du compte Instagram livrés dans la même fenêtre.",
      },
    ],
    metrics: [
      { value: "×3", label: "demandes de devis qualifiées", detail: "90 jours après lancement" },
      { value: "6 sem.", label: "du positionnement au site en ligne" },
      { value: "12 → 5", label: "couleurs dans l’identité" },
      { value: "+38 %", label: "panier moyen", detail: "grâce au catalogue structuré" },
    ],
    testimonial: {
      id: "t-mora",
      quote:
        "Je pensais avoir besoin d’un logo. J’avais besoin de savoir quoi refuser. Depuis, je ne repars plus de zéro à chaque publication — et mes clients répètent ma phrase de positionnement mot pour mot.",
      author: "Léa Mora",
      role: "Fondatrice, Atelier Mora",
      initials: "LM",
    },
    before: {
      label: "Avant",
      palette: ["#B8A99A", "#7C9CA6", "#D9C7B0", "#4A4A4A"],
      typeface: "4 polices différentes selon les supports",
      notes: [
        "Trois versions du logo en circulation",
        "Bio interchangeable avec n’importe quel concurrent",
        "Aucune règle d’application écrite",
      ],
    },
    after: {
      label: "Après",
      palette: ["#1F2933", "#C9722F", "#EDE6DB", "#7A8B8F"],
      typeface: "1 police, 2 graisses",
      notes: [
        "Un lockup unique, décliné en 3 formats",
        "Une promesse en 14 mots, testée auprès de 5 restaurateurs",
        "20 règles d’application documentées",
      ],
    },
    cta: {
      kind: "product",
      slug: "kit-brandos-roadmap",
      label: "Voir le Kit BrandOS & Roadmap",
    },
  },
  {
    slug: "north-consulting",
    client: "North Consulting",
    sector: "Conseil B2B",
    headline: "Sortir de la concurrence par le prix en clarifiant l’offre",
    excerpt:
      "Un consultant indépendant confondu avec les grandes structures. Repositionnement sur une niche, refonte de l’offre et de la voix.",
    keyMetric: {
      value: "+45 %",
      label: "de tarif journalier moyen",
      detail: "sans perte de volume",
    },
    context: [
      "North Consulting accompagnait des PME industrielles sur leurs process. Bon carnet d’adresses, excellentes recommandations — et une marque qui ressemblait à celle d’un cabinet de 200 personnes.",
      "Résultat : à chaque appel d’offres, la comparaison se faisait sur le prix. Le positionnement « conseil en organisation » n’aidait personne à comprendre pourquoi payer plus cher un indépendant.",
    ],
    method: [
      {
        step: "01",
        title: "Nommer la vraie spécialité",
        body: "Derrière « conseil en organisation », il y avait un savoir-faire précis : la reprise de sites industriels après rachat. C’est devenu la promesse.",
      },
      {
        step: "02",
        title: "Restructurer l’offre",
        body: "Trois offres lisibles avec un livrable nommé chacune, au lieu d’un devis sur mesure à chaque fois.",
      },
      {
        step: "03",
        title: "Aligner l’identité sur le niveau de prix",
        body: "Une identité sobre et dense, pensée pour des documents longs et des slides de comité, pas pour des posts.",
      },
      {
        step: "04",
        title: "Réécrire les surfaces commerciales",
        body: "LinkedIn, propositions commerciales et page d’accueil réécrits à partir du même guide de voix.",
      },
    ],
    metrics: [
      { value: "+45 %", label: "tarif journalier moyen" },
      { value: "3", label: "offres nommées", detail: "au lieu du sur-mesure systématique" },
      { value: "−60 %", label: "de temps passé à rédiger des propositions" },
      { value: "8 sem.", label: "durée du repositionnement" },
    ],
    testimonial: {
      id: "t-north",
      quote:
        "Le déclic, c’est d’avoir accepté de refuser 40 % des missions. Depuis, on ne me compare plus à un cabinet : on m’appelle pour ce que je fais précisément.",
      author: "Julien Renard",
      role: "Fondateur, North Consulting",
      initials: "JR",
    },
    before: {
      label: "Avant",
      palette: ["#2B5CA8", "#6B9BD1", "#A8C4E0", "#606060"],
      typeface: "Police système, aucune hiérarchie",
      notes: [
        "Identité générique de cabinet de conseil",
        "Offre sur mesure impossible à comparer",
        "Aucune preuve visible sur le site",
      ],
    },
    after: {
      label: "Après",
      palette: ["#111827", "#B45309", "#F4F1EC", "#4B5563"],
      typeface: "1 serif de titre + 1 sans-serif de texte",
      notes: [
        "Positionnement sur la reprise post-acquisition",
        "3 offres nommées et chiffrées",
        "Une étude de cas par offre",
      ],
    },
    cta: {
      kind: "course",
      slug: "formation-brandos",
      label: "Découvrir la formation",
    },
  },
  {
    slug: "kova-studio",
    client: "Kova Studio",
    sector: "Studio créatif",
    headline: "Deux associés, une seule marque : aligner les voix",
    excerpt:
      "Un duo de motion designers qui publiait deux discours différents. Un système commun pour arrêter de se contredire.",
    keyMetric: {
      value: "−70 %",
      label: "de temps de production des visuels",
      detail: "grâce aux gabarits",
    },
    context: [
      "Kova Studio, c’est deux associés et deux sensibilités. Sur le papier, une richesse ; en pratique, deux marques qui se chevauchaient : deux façons d’écrire, deux traitements visuels, deux idées de la cible.",
      "Les prospects, eux, ne voyaient qu’une incohérence — et posaient systématiquement la question : « vous faites quoi, exactement ? »",
    ],
    method: [
      {
        step: "01",
        title: "Arbitrer à deux",
        body: "Une séance de tranchage : chaque désaccord de positionnement documenté, puis arbitré définitivement. Les décisions ont été écrites, pas mémorisées.",
      },
      {
        step: "02",
        title: "Un seul guide de voix",
        body: "Un document commun avec exemples et contre-exemples pour chaque axe de ton. Les deux associés écrivent désormais à partir de la même base.",
      },
      {
        step: "03",
        title: "Industrialiser les visuels",
        body: "Douze gabarits couvrant tous les formats publiés. Le studio produit maintenant une semaine de contenu en une heure.",
      },
    ],
    metrics: [
      { value: "−70 %", label: "temps de production des visuels" },
      { value: "12", label: "gabarits couvrant tous les formats" },
      { value: "1", label: "guide de voix pour deux associés" },
      { value: "+22 %", label: "taux de réponse aux prises de contact" },
    ],
    testimonial: {
      id: "t-kova",
      quote:
        "On a passé deux ans à croire qu’on avait un problème de goût. On avait un problème d’arbitrage. Écrire les décisions a réglé 80 % des débats.",
      author: "Sacha Belin",
      role: "Co-fondateur, Kova Studio",
      initials: "SB",
    },
    before: {
      label: "Avant",
      palette: ["#E8452E", "#3D8BD4", "#F2C94C", "#8E44AD"],
      typeface: "3 polices display concurrentes",
      notes: [
        "Deux traitements visuels selon l’associé qui publie",
        "Ligne éditoriale contradictoire",
        "Chaque visuel refait de zéro",
      ],
    },
    after: {
      label: "Après",
      palette: ["#181818", "#E8452E", "#F5F3EF", "#6E6E73"],
      typeface: "1 display + 1 texte, échelle à 6 niveaux",
      notes: [
        "Une seule signature visuelle, deux signatures humaines",
        "12 gabarits verrouillés",
        "Décisions de marque écrites et datées",
      ],
    },
    cta: {
      kind: "product",
      slug: "systeme-identite-visuelle",
      label: "Voir le Système d’identité visuelle",
    },
  },
  {
    slug: "veri-nutrition",
    client: "Véri Nutrition",
    sector: "Santé & bien-être",
    headline: "Crédibiliser une marque santé sans tomber dans le jargon",
    excerpt:
      "Une diététicienne indépendante coincée entre le ton médical et le ton wellness. Une voix de marque qui tranche.",
    keyMetric: {
      value: "+61 %",
      label: "d’inscriptions à la newsletter",
      detail: "après refonte de la voix",
    },
    context: [
      "Véri Nutrition hésitait entre deux registres : un ton clinique qui rassurait sans donner envie, et un ton wellness qui donnait envie sans rassurer. Les deux coexistaient sur le même site.",
      "Cette hésitation coûtait cher : les visiteurs ne savaient pas s’ils avaient affaire à une professionnelle de santé ou à une coach lifestyle.",
    ],
    method: [
      {
        step: "01",
        title: "Choisir un registre",
        body: "Le pari : rigueur du fond, simplicité de la forme. On cite les sources, on explique en langage courant, on ne promet jamais de résultat chiffré.",
      },
      {
        step: "02",
        title: "Écrire les interdits",
        body: "Une liste de 30 mots bannis — « détox », « brûle-graisse », « miracle » — qui a nettoyé l’ensemble des contenus existants.",
      },
      {
        step: "03",
        title: "Habiller en conséquence",
        body: "Une identité claire, beaucoup de blanc, une seule couleur d’accent. Rien qui évoque le supplément alimentaire.",
      },
      {
        step: "04",
        title: "Installer un rituel éditorial",
        body: "Une publication longue par mois, quatre formats courts dérivés. Le rituel tient depuis huit mois.",
      },
    ],
    metrics: [
      { value: "+61 %", label: "inscriptions newsletter" },
      { value: "30", label: "mots bannis documentés" },
      { value: "8 mois", label: "de rituel éditorial tenu" },
      { value: "×2,4", label: "durée moyenne de session sur le site" },
    ],
    testimonial: {
      id: "t-veri",
      quote:
        "La liste de mots bannis a été l’outil le plus utile de tout le parcours. En supprimant ce vocabulaire, j’ai enfin trouvé comment parler comme moi.",
      author: "Anaïs Cordier",
      role: "Diététicienne-nutritionniste, Véri Nutrition",
      initials: "AC",
    },
    before: {
      label: "Avant",
      palette: ["#7BC47F", "#A8D5BA", "#F7D794", "#5E8B7E"],
      typeface: "Script décorative + sans-serif",
      notes: [
        "Ton oscillant entre médical et wellness",
        "Vocabulaire marketing non maîtrisé",
        "Aucune source citée",
      ],
    },
    after: {
      label: "Après",
      palette: ["#14211C", "#2F6B4F", "#FBFAF7", "#79807C"],
      typeface: "1 sans-serif humaniste, 3 graisses",
      notes: [
        "Un registre unique : rigoureux et lisible",
        "30 mots bannis, appliqués partout",
        "Sources citées sur chaque contenu long",
      ],
    },
    cta: {
      kind: "product",
      slug: "bibliotheque-prompts-ia",
      label: "Voir la Bibliothèque de prompts",
    },
  },
];

export function getCaseStudy(slug: string): CaseStudy | undefined {
  return caseStudies.find((c) => c.slug === slug);
}

export const caseStudySectors = Array.from(
  new Set(caseStudies.map((c) => c.sector)),
);
