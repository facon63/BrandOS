/* ============================================================================
   Types du domaine BrandOS.
   Ces interfaces décrivent le contrat attendu par les composants UI.
   Elles sont volontairement plates et sérialisables : le jour où les données
   viennent d’un CMS (Sanity, Notion API, Payload…), seul le module `data/*`
   change — pas les composants.
   ========================================================================= */

export type ProductType = "notion" | "pdf" | "bundle";

export interface ProductFeature {
  label: string;
  detail: string;
}

export interface Product {
  slug: string;
  name: string;
  tagline: string;
  /** Description courte, utilisée sur les cards de la boutique. */
  excerpt: string;
  /** Description longue, page produit. Un paragraphe par entrée. */
  description: string[];
  type: ProductType;
  /** Prix en euros, TTC. `compareAtPrice` = prix barré si promo. */
  price: number;
  compareAtPrice?: number;
  badge?: "Best-seller" | "Nouveau" | "Bundle";
  /** Bénéfices en bullet points sur la fiche produit. */
  benefits: string[];
  /** Contenu inclus, affiché en liste chiffrée. */
  includes: ProductFeature[];
  /** Galerie : visuels mockés, à remplacer par de vraies captures. */
  gallery: MockVisual[];
  /** Slugs de produits suggérés en cross-sell. */
  related: string[];
  featured?: boolean;
}

/**
 * Visuel « mocké » : on ne dispose pas encore des captures produit réelles.
 * Le composant `MockShot` rend un aperçu stylisé à partir de ces métadonnées.
 * TODO (phase 2) : remplacer par `{ src: string; alt: string; width; height }`.
 */
export interface MockVisual {
  id: string;
  /** Légende affichée sous / dans le visuel. */
  caption: string;
  /** Variante de rendu du placeholder. */
  kind: "dashboard" | "database" | "checklist" | "palette" | "prompts" | "cover";
}

export interface Lesson {
  id: string;
  title: string;
  /** Durée en minutes. */
  duration: number;
  /** Statut simulé de l’espace membre. TODO (phase 2) : venir de l’API. */
  status: "done" | "in-progress" | "todo";
  /** Leçon offerte en aperçu public. */
  preview?: boolean;
}

export interface CourseModule {
  id: string;
  index: number;
  title: string;
  promise: string;
  description: string;
  lessons: Lesson[];
  /** Ressources téléchargeables rattachées au module (mock). */
  resources: { label: string; format: "PDF" | "Notion" | "Figma" | "CSV" }[];
}

export interface Course {
  slug: string;
  name: string;
  tagline: string;
  price: number;
  compareAtPrice?: number;
  /** Durée totale en minutes, calculée à partir des leçons. */
  totalLessons: number;
  totalDuration: number;
  modules: CourseModule[];
  includes: string[];
  forWho: string[];
  notForWho: string[];
}

export interface CaseStudyMetric {
  value: string;
  label: string;
  detail?: string;
}

export interface CaseStudy {
  slug: string;
  client: string;
  sector: string;
  /** Phrase-résultat affichée sur la card. */
  headline: string;
  excerpt: string;
  /** Résultat clé mis en avant sur la vignette. */
  keyMetric: CaseStudyMetric;
  context: string[];
  /** Étapes du système BrandOS réellement appliquées. */
  method: { step: string; title: string; body: string }[];
  metrics: CaseStudyMetric[];
  testimonial: Testimonial;
  /** Palette avant / après, pour le comparateur visuel. */
  before: BrandSnapshot;
  after: BrandSnapshot;
  /** CTA de fin d’étude : produit ou formation utilisés. */
  cta: { kind: "product" | "course"; slug: string; label: string };
  featured?: boolean;
}

export interface BrandSnapshot {
  label: string;
  /** 4 couleurs hex décrivant l’identité (avant = incohérente). */
  palette: string[];
  typeface: string;
  /** Points d’observation listés sous le visuel. */
  notes: string[];
}

export interface Testimonial {
  id: string;
  quote: string;
  author: string;
  role: string;
  /** Initiales affichées à la place de la photo (photos non fournies). */
  initials: string;
}

export interface FaqItem {
  question: string;
  answer: string;
  category: FaqCategory;
}

export type FaqCategory =
  | "Produits"
  | "Formation"
  | "Facturation"
  | "Technique";

export interface CartLine {
  slug: string;
  name: string;
  type: "product" | "course";
  price: number;
  quantity: number;
}
