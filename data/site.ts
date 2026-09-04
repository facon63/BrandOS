/* Configuration globale du site : navigation, footer, réassurance.
   Données de démonstration — les chiffres marqués « placeholder » sont à
   remplacer par les vrais indicateurs avant mise en ligne. */

export const site = {
  name: "BrandOS",
  baseline: "Le système d’exploitation de ta marque personnelle",
  description:
    "Positionnement, identité visuelle, voix, organisation : BrandOS structure tout ce qu’il te faut pour lancer une marque qui a de l’allure — sans agence, sans flou.",
  email: "bonjour@brandos.studio",
  url: "https://brandos.studio",
} as const;

export const mainNav = [
  { href: "/produits", label: "Produits" },
  { href: "/formation", label: "Formation" },
  { href: "/etudes-de-cas", label: "Études de cas" },
  { href: "/a-propos", label: "À propos" },
  { href: "/contact", label: "Contact" },
] as const;

export const footerNav = [
  {
    title: "Le système",
    links: [
      { href: "/produits", label: "Produits digitaux" },
      { href: "/formation", label: "Formation vidéo" },
      { href: "/formation/programme", label: "Programme détaillé" },
      { href: "/tarifs", label: "Tarifs" },
    ],
  },
  {
    title: "Preuves",
    links: [
      { href: "/etudes-de-cas", label: "Études de cas" },
      { href: "/a-propos", label: "Manifeste" },
      { href: "/faq", label: "FAQ" },
    ],
  },
  {
    title: "Compte",
    links: [
      { href: "/compte", label: "Connexion" },
      { href: "/espace-membre", label: "Espace membre" },
      { href: "/panier", label: "Panier" },
      { href: "/contact", label: "Nous écrire" },
    ],
  },
] as const;

/* Placeholders réseaux sociaux — remplacer par les vraies URLs. */
export const socials = [
  { label: "LinkedIn", href: "#", handle: "/in/brandos" },
  { label: "Instagram", href: "#", handle: "@brandos.studio" },
  { label: "YouTube", href: "#", handle: "/@brandos" },
] as const;

/* Bandeau de réassurance — CHIFFRES PLACEHOLDER, à valider avant publication. */
export const trustStats = [
  { value: "500+", label: "solopreneurs structurés" },
  { value: "12", label: "secteurs d’activité couverts" },
  { value: "24", label: "actions dans la checklist Launch-Ready" },
  { value: "4,9/5", label: "note moyenne des acheteurs" },
] as const;

export const legalNotice =
  "Mentions légales, CGV et politique de confidentialité — contenus à rédiger avant mise en ligne.";
