import type { Product } from "@/lib/types";

/* ============================================================================
   Catalogue produits — DONNÉES DE DÉMONSTRATION.
   Structure stable : un CMS n’aura qu’à fournir le même tableau.
   ========================================================================= */

export const products: Product[] = [
  {
    slug: "kit-brandos-roadmap",
    name: "Kit BrandOS & Roadmap",
    tagline: "Le système complet, installé en une après-midi",
    excerpt:
      "Le cœur du système : espace Notion interactif, dashboard de suivi, bibliothèque de prompts IA et checklist Launch-Ready.",
    description: [
      "Le Kit BrandOS & Roadmap, c’est l’installation complète du système. Tu dupliques l’espace Notion, tu réponds aux questions guidées, et ta marque passe d’une intuition floue à une structure documentée : positionnement, territoire visuel, voix, rituels de publication.",
      "Rien n’est laissé à l’inspiration du moment. Chaque base de données est reliée aux autres : ton positionnement alimente ta voix, ta voix alimente tes prompts IA, tes prompts alimentent ta roadmap de lancement. C’est un système, pas une collection de templates.",
      "La Roadmap, elle, transforme tout ça en calendrier. 24 actions ordonnées, chacune avec son critère de fin. Tu sais toujours quelle est la prochaine chose à faire.",
    ],
    type: "bundle",
    price: 149,
    compareAtPrice: 197,
    badge: "Best-seller",
    featured: true,
    benefits: [
      "Sortir du syndrome « je refais mon logo tous les trois mois »",
      "Documenter ta marque une fois pour que chaque publication soit cohérente",
      "Déléguer sans réexpliquer : ton système est lisible par un freelance en 10 minutes",
      "Avancer par étapes courtes plutôt que par grandes remises en question",
    ],
    includes: [
      {
        label: "6 bases de données Notion reliées",
        detail:
          "Positionnement, Territoire visuel, Voix & messages, Offres, Roadmap de lancement, Bibliothèque d’assets.",
      },
      {
        label: "Dashboard de suivi",
        detail:
          "Progression globale, prochaine action, état de chaque pilier en un coup d'œil.",
      },
      {
        label: "Checklist PDF Launch-Ready — 24 actions",
        detail:
          "Version imprimable du parcours, avec critère de validation pour chaque action.",
      },
      {
        label: "12 prompts IA calibrés",
        detail:
          "Prompts pré-remplis avec ton positionnement pour rédiger bio, page à propos, posts et pitch.",
      },
      {
        label: "Générateur de palette",
        detail:
          "Méthode + grille de test contraste pour verrouiller 5 couleurs qui tiennent en usage réel.",
      },
      {
        label: "Mises à jour à vie",
        detail:
          "Chaque nouvelle version du système arrive dans ton espace, sans surcoût.",
      },
    ],
    gallery: [
      { id: "g1", caption: "Dashboard de suivi BrandOS", kind: "dashboard" },
      { id: "g2", caption: "Base de données Positionnement", kind: "database" },
      { id: "g3", caption: "Bibliothèque de prompts IA", kind: "prompts" },
      { id: "g4", caption: "Générateur de palette", kind: "palette" },
    ],
    related: ["checklist-launch-ready", "bibliotheque-prompts-ia"],
  },
  {
    slug: "checklist-launch-ready",
    name: "Checklist Launch-Ready",
    tagline: "24 actions entre « j’y pense » et « c’est en ligne »",
    excerpt:
      "Le parcours de lancement en 24 actions ordonnées, avec pour chacune un critère de fin non négociable.",
    description: [
      "La plupart des lancements ne échouent pas par manque d’idées, mais par manque d’ordre. On refait la page d’accueil avant d’avoir écrit la promesse ; on choisit une police avant de savoir à qui on parle.",
      "La Checklist Launch-Ready remet les actions dans le bon ordre et, surtout, donne à chacune un critère de fin. Pas « travailler mon positionnement », mais « une phrase de positionnement de moins de 20 mots, validée par 3 personnes de ta cible ».",
      "24 actions, 4 phases, un PDF que tu peux imprimer et cocher au stylo.",
    ],
    type: "pdf",
    price: 29,
    badge: "Nouveau",
    benefits: [
      "Savoir exactement quelle est ta prochaine action",
      "Arrêter de tourner sur les tâches confortables (le logo) au lieu des tâches utiles (la promesse)",
      "Un critère de fin par action : plus de tâche « en cours » pendant six semaines",
    ],
    includes: [
      {
        label: "24 actions en 4 phases",
        detail: "Clarifier · Habiller · Écrire · Déployer.",
      },
      {
        label: "Critère de validation par action",
        detail: "Une définition du « terminé » qui ne se négocie pas.",
      },
      {
        label: "PDF imprimable A4",
        detail: "Mise en page pensée pour être affichée au mur.",
      },
      {
        label: "Version Notion cochable",
        detail: "Pour celles et ceux qui vivent dans leur espace de travail.",
      },
    ],
    gallery: [
      { id: "g1", caption: "Checklist Launch-Ready, phase 1", kind: "checklist" },
      { id: "g2", caption: "Couverture du PDF", kind: "cover" },
    ],
    related: ["kit-brandos-roadmap", "systeme-identite-visuelle"],
  },
  {
    slug: "bibliotheque-prompts-ia",
    name: "Bibliothèque de prompts IA",
    tagline: "Ton positionnement, injecté dans chaque prompt",
    excerpt:
      "48 prompts structurés pour écrire avec ta voix — bio, page à propos, posts, séquences email, pitch.",
    description: [
      "Un prompt générique produit un texte générique. Le problème n’est pas l’IA : c’est qu’on lui demande d’écrire pour « un freelance » au lieu de lui donner un positionnement, une voix et des interdits.",
      "La bibliothèque fonctionne en deux temps. Tu remplis une fois ton « bloc de marque » (promesse, cible, ton, mots bannis). Ensuite, chaque prompt s’appuie dessus automatiquement.",
      "48 prompts couvrant les 6 surfaces où ta marque s’exprime vraiment.",
    ],
    type: "notion",
    price: 49,
    benefits: [
      "Des textes qui sonnent comme toi, pas comme un assistant",
      "Un bloc de marque à remplir une fois, réutilisé partout",
      "Des prompts testés sur des cas réels, pas des formules à rallonge",
    ],
    includes: [
      {
        label: "48 prompts classés par surface",
        detail: "Site, réseaux, email, pitch, offres, service client.",
      },
      {
        label: "Bloc de marque réutilisable",
        detail: "Un bloc unique qui s’insère au début de chaque prompt.",
      },
      {
        label: "Liste de mots bannis",
        detail: "Le vocabulaire qui trahit une marque écrite à la va-vite.",
      },
      {
        label: "Exemples avant / après",
        detail: "Le même prompt, sans puis avec bloc de marque.",
      },
    ],
    gallery: [
      { id: "g1", caption: "Bibliothèque de prompts, vue galerie", kind: "prompts" },
      { id: "g2", caption: "Bloc de marque à remplir", kind: "database" },
    ],
    related: ["kit-brandos-roadmap", "checklist-launch-ready"],
  },
  {
    slug: "systeme-identite-visuelle",
    name: "Système d’identité visuelle",
    tagline: "Une identité qui tient en usage réel, pas juste sur une planche",
    excerpt:
      "Le module visuel isolé : méthode de palette, échelle typographique, grille et règles d’application.",
    description: [
      "Une identité visuelle qui ne tient pas la route, c’est toujours la même histoire : elle est belle sur une planche d’inspiration et impossible à appliquer sur une story, une facture ou une slide.",
      "Ce module isole la partie visuelle du système BrandOS. Tu construis une palette testée en contraste, une échelle typographique à 6 niveaux, une grille d’espacement, et surtout les règles d’application qui rendent tout ça utilisable au quotidien.",
      "C’est le module recommandé si ton positionnement est déjà clair et que seul l’habillage cloche.",
    ],
    type: "notion",
    price: 69,
    benefits: [
      "Une palette validée en contraste, utilisable en accessibilité",
      "Une échelle typographique cohérente du titre au caption",
      "Des règles d’application écrites : plus d’hésitation à chaque visuel",
    ],
    includes: [
      {
        label: "Méthode de palette en 5 couleurs",
        detail: "Une principale, une sombre, un accent, deux neutres.",
      },
      {
        label: "Grille de test contraste",
        detail: "Chaque combinaison texte/fond évaluée avant validation.",
      },
      {
        label: "Échelle typographique à 6 niveaux",
        detail: "Du display au caption, avec interlignage associé.",
      },
      {
        label: "20 règles d’application",
        detail: "Ce qu’on fait, ce qu’on ne fait jamais.",
      },
    ],
    gallery: [
      { id: "g1", caption: "Générateur et test de palette", kind: "palette" },
      { id: "g2", caption: "Échelle typographique", kind: "database" },
    ],
    related: ["kit-brandos-roadmap", "bibliotheque-prompts-ia"],
  },
  {
    slug: "pack-lancement-complet",
    name: "Pack Lancement complet",
    tagline: "Tout le système, plus la formation vidéo",
    excerpt:
      "Le Kit BrandOS, la Checklist, la bibliothèque de prompts et l’accès à la formation vidéo — au tarif groupé.",
    description: [
      "Le pack pour celles et ceux qui veulent le système ET la méthode. Tu récupères l’intégralité des produits digitaux, plus l’accès à vie à la formation vidéo et à son espace membre.",
      "C’est le chemin le plus court entre « ma marque part dans tous les sens » et « ma marque est installée, documentée et en ligne ».",
    ],
    type: "bundle",
    price: 379,
    compareAtPrice: 544,
    badge: "Bundle",
    featured: true,
    benefits: [
      "Tous les produits digitaux, sans exception",
      "Accès à vie à la formation vidéo et à ses mises à jour",
      "Un seul parcours, du positionnement au lancement",
      "Environ 30 % d’économie par rapport aux achats séparés",
    ],
    includes: [
      { label: "Kit BrandOS & Roadmap", detail: "Le système Notion complet." },
      { label: "Checklist Launch-Ready", detail: "Les 24 actions de lancement." },
      { label: "Bibliothèque de prompts IA", detail: "Les 48 prompts calibrés." },
      { label: "Système d’identité visuelle", detail: "Le module visuel isolé." },
      {
        label: "Formation vidéo — 5 modules",
        detail: "Accès à vie à l’espace membre et aux mises à jour.",
      },
    ],
    gallery: [
      { id: "g1", caption: "Vue d’ensemble du pack", kind: "cover" },
      { id: "g2", caption: "Dashboard de suivi", kind: "dashboard" },
      { id: "g3", caption: "Espace membre formation", kind: "checklist" },
    ],
    related: ["kit-brandos-roadmap", "systeme-identite-visuelle"],
  },
];

export const productTypeLabels: Record<Product["type"], string> = {
  notion: "Template Notion",
  pdf: "Checklist PDF",
  bundle: "Bundle",
};

export function getProduct(slug: string): Product | undefined {
  return products.find((p) => p.slug === slug);
}

export function getProducts(slugs: readonly string[]): Product[] {
  return slugs
    .map((slug) => getProduct(slug))
    .filter((p): p is Product => Boolean(p));
}
