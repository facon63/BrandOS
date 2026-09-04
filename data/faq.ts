import type { FaqItem } from "@/lib/types";

/* FAQ complète, catégorisée. Les 4 premières entrées `Produits` alimentent
   également la FAQ courte de la page d’accueil. */

export const faq: FaqItem[] = [
  {
    category: "Produits",
    question: "BrandOS, c’est un template ou une méthode ?",
    answer:
      "Les deux, et c’est le point. Le template seul ne sert à rien si tu ne sais pas quoi y mettre ; la méthode seule finit dans un carnet. BrandOS est un système : des bases de données Notion reliées entre elles, alimentées par un parcours de décisions qui te dit quoi trancher et dans quel ordre.",
  },
  {
    category: "Produits",
    question: "Faut-il savoir utiliser Notion ?",
    answer:
      "Non. Tu dupliques l’espace en un clic et tout est déjà structuré : tu remplis des champs, tu coches des cases. Une vidéo de prise en main de 6 minutes est incluse. Si tu sais utiliser un tableur, tu sais utiliser le Kit BrandOS.",
  },
  {
    category: "Produits",
    question: "Combien de temps faut-il pour installer le système ?",
    answer:
      "Une après-midi pour l’installation et le premier passage complet. Compte ensuite deux à six semaines pour dérouler les 24 actions de la Roadmap, selon le temps que tu y consacres chaque semaine. Les utilisateurs les plus rapides bouclent en trois week-ends.",
  },
  {
    category: "Produits",
    question: "Et si j’ai déjà une identité visuelle ?",
    answer:
      "Tant mieux : BrandOS sert alors à la documenter et à la rendre applicable. La plupart des marques n’ont pas un problème d’esthétique mais un problème de règles — rien n’est écrit, donc tout est renégocié à chaque visuel. Le module Identité visuelle audite l’existant avant de proposer quoi que ce soit.",
  },
  {
    category: "Produits",
    question: "Les produits sont-ils mis à jour ?",
    answer:
      "Oui, et les mises à jour sont incluses à vie. Quand une nouvelle version du système sort, elle apparaît dans ton espace dupliqué via un lien de synchronisation, sans surcoût et sans manipulation de ta part.",
  },
  {
    category: "Formation",
    question: "Quelle est la différence entre le Kit et la formation ?",
    answer:
      "Le Kit te donne la structure : les bases de données, la roadmap, les prompts. La formation t’explique comment prendre les décisions qui remplissent cette structure — pourquoi ce positionnement plutôt qu’un autre, comment tester une palette, comment documenter une voix. Le Kit est d’ailleurs inclus dans la formation.",
  },
  {
    category: "Formation",
    question: "Combien de temps dure la formation ?",
    answer:
      "Environ 6 heures de vidéo réparties sur 5 modules et 22 leçons, plus les ateliers pratiques. En rythme réaliste — une leçon et son exercice par jour ouvré — compte quatre à cinq semaines pour aller au bout.",
  },
  {
    category: "Formation",
    question: "Y a-t-il un accompagnement individuel ?",
    answer:
      "Pas dans l’offre actuelle : la formation est en autonomie complète, avec des ateliers guidés et des critères de validation pour chaque étape. Un format accompagné est à l’étude — écris-nous si le sujet t’intéresse, cela nous aide à le prioriser.",
  },
  {
    category: "Formation",
    question: "L’accès est-il limité dans le temps ?",
    answer:
      "Non. L’accès est à vie, mises à jour comprises. Tu peux interrompre pendant six mois et reprendre exactement là où tu t’étais arrêté : l’espace membre conserve ta progression leçon par leçon.",
  },
  {
    category: "Facturation",
    question: "Puis-je payer en plusieurs fois ?",
    answer:
      "Le paiement en trois fois sans frais sera disponible au lancement de la boutique, sur la formation et les bundles. Les produits unitaires resteront en paiement comptant.",
  },
  {
    category: "Facturation",
    question: "Une facture est-elle fournie ?",
    answer:
      "Oui, une facture au format PDF est envoyée automatiquement après l’achat, avec la mention de TVA correspondant à ton pays de facturation. Elle reste accessible depuis ton compte.",
  },
  {
    category: "Facturation",
    question: "Quelle est la politique de remboursement ?",
    answer:
      "Garantie 30 jours sur la formation et les bundles, sans justification à fournir : un e-mail suffit. Les produits numériques unitaires téléchargés ne sont pas remboursables, conformément au droit applicable aux contenus numériques livrés immédiatement.",
  },
  {
    category: "Technique",
    question: "Sur quels appareils puis-je suivre la formation ?",
    answer:
      "L’espace membre fonctionne sur ordinateur, tablette et mobile, dans le navigateur, sans application à installer. Les ressources téléchargeables sont au format PDF, Notion ou Figma selon les modules.",
  },
  {
    category: "Technique",
    question: "Les vidéos sont-elles sous-titrées ?",
    answer:
      "Oui, sous-titres français sur l’intégralité des leçons, avec transcription téléchargeable module par module.",
  },
  {
    category: "Technique",
    question: "Puis-je utiliser BrandOS pour plusieurs marques ?",
    answer:
      "La licence couvre une personne et ses propres marques, sans limite de nombre. Pour utiliser le système avec des clients dans un cadre professionnel — agence, studio, freelance branding — une licence pro est nécessaire : contacte-nous.",
  },
];

export const faqCategories = ["Produits", "Formation", "Facturation", "Technique"] as const;

/** Sélection courte pour la page d’accueil. */
export const homeFaq = [faq[0], faq[3], faq[5], faq[11]];
