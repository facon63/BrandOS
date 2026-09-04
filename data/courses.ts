import type { Course, CourseModule } from "@/lib/types";

/* ============================================================================
   Formation vidéo — DONNÉES DE DÉMONSTRATION.
   Les statuts de leçon (`done` / `in-progress` / `todo`) simulent la
   progression d’un membre connecté.
   TODO (phase 2) : remplacer par la progression réelle de l’utilisateur.
   ========================================================================= */

const modules: CourseModule[] = [
  {
    id: "m1",
    index: 1,
    title: "Poser le socle",
    promise: "Une promesse de marque en une phrase, tenable et vérifiable.",
    description:
      "On commence par le seul travail qui rend tout le reste possible : savoir à qui tu parles, de quoi tu réponds, et ce que tu refuses. Sans ça, chaque décision visuelle devient un coup de dés.",
    lessons: [
      { id: "l1", title: "Pourquoi ta marque part dans tous les sens", duration: 9, status: "done", preview: true },
      { id: "l2", title: "Cartographier ta cible réelle (pas la cible rêvée)", duration: 16, status: "done" },
      { id: "l3", title: "Écrire ta promesse en moins de 20 mots", duration: 21, status: "done" },
      { id: "l4", title: "Définir tes trois refus", duration: 12, status: "done" },
      { id: "l5", title: "Atelier : valider ta promesse auprès de 3 personnes", duration: 14, status: "done" },
    ],
    resources: [
      { label: "Canevas de positionnement", format: "Notion" },
      { label: "Grille de validation de promesse", format: "PDF" },
    ],
  },
  {
    id: "m2",
    index: 2,
    title: "Habiller le système",
    promise: "Une identité visuelle applicable partout, testée en contraste.",
    description:
      "L’identité visuelle n’est pas une planche d’inspiration : c’est un jeu de contraintes. On construit une palette, une échelle typographique et une grille, puis on les met à l’épreuve sur des supports réels.",
    lessons: [
      { id: "l1", title: "Choisir 5 couleurs, pas 15", duration: 18, status: "done" },
      { id: "l2", title: "Tester ta palette en contraste réel", duration: 13, status: "in-progress" },
      { id: "l3", title: "Construire une échelle typographique", duration: 19, status: "todo" },
      { id: "l4", title: "Le rythme : espacement, grille, respiration", duration: 15, status: "todo" },
      { id: "l5", title: "Atelier : appliquer l’identité à 4 supports", duration: 24, status: "todo", preview: true },
    ],
    resources: [
      { label: "Générateur de palette", format: "Notion" },
      { label: "Grille typographique", format: "Figma" },
      { label: "Test de contraste", format: "CSV" },
    ],
  },
  {
    id: "m3",
    index: 3,
    title: "Trouver la voix",
    promise: "Un ton reconnaissable, documenté, réutilisable par l’IA.",
    description:
      "Ta voix, ce n’est pas « être authentique ». C’est un ensemble de choix : le niveau de langue, la longueur des phrases, ce que tu nommes et ce que tu ne nommes jamais. On la documente pour qu’elle survive à la fatigue du vendredi soir.",
    lessons: [
      { id: "l1", title: "Les quatre axes d’un ton de marque", duration: 17, status: "todo" },
      { id: "l2", title: "Ta liste de mots bannis", duration: 11, status: "todo" },
      { id: "l3", title: "Écrire ta bio, ta page à propos, ton pitch", duration: 26, status: "todo" },
      { id: "l4", title: "Calibrer l’IA sur ta voix", duration: 20, status: "todo" },
    ],
    resources: [
      { label: "Guide de voix de marque", format: "Notion" },
      { label: "Bibliothèque de prompts", format: "Notion" },
    ],
  },
  {
    id: "m4",
    index: 4,
    title: "Organiser l’exécution",
    promise: "Un rythme de publication qui tient sans motivation.",
    description:
      "Une marque cohérente est d’abord une marque régulière. On installe les rituels, les gabarits et le système de fichiers qui rendent la publication ennuyeuse — donc durable.",
    lessons: [
      { id: "l1", title: "Le rituel hebdomadaire en 45 minutes", duration: 14, status: "todo" },
      { id: "l2", title: "Gabarits : produire 10 visuels en une heure", duration: 22, status: "todo" },
      { id: "l3", title: "Nommer et ranger tes assets", duration: 10, status: "todo" },
      { id: "l4", title: "Déléguer sans réexpliquer", duration: 16, status: "todo" },
    ],
    resources: [
      { label: "Rituel hebdomadaire", format: "Notion" },
      { label: "Convention de nommage", format: "PDF" },
    ],
  },
  {
    id: "m5",
    index: 5,
    title: "Déployer",
    promise: "Un lancement daté, avec un critère de fin pour chaque étape.",
    description:
      "La partie que tout le monde repousse. On transforme la roadmap en calendrier daté, on prépare les surfaces, et on lance — même si tout n’est pas parfait, parce que ça ne le sera jamais.",
    lessons: [
      { id: "l1", title: "Transformer la roadmap en dates", duration: 13, status: "todo" },
      { id: "l2", title: "Préparer tes surfaces : site, réseaux, email", duration: 23, status: "todo" },
      { id: "l3", title: "La semaine de lancement, jour par jour", duration: 18, status: "todo" },
      { id: "l4", title: "Mesurer, ajuster, ne pas tout refaire", duration: 15, status: "todo" },
    ],
    resources: [
      { label: "Checklist Launch-Ready", format: "PDF" },
      { label: "Calendrier de lancement", format: "Notion" },
    ],
  },
];

const totalLessons = modules.reduce((n, m) => n + m.lessons.length, 0);
const totalDuration = modules.reduce(
  (n, m) => n + m.lessons.reduce((s, l) => s + l.duration, 0),
  0,
);

export const course: Course = {
  slug: "formation-brandos",
  name: "Formation BrandOS",
  tagline: "Construire ta marque étape par étape, en 5 modules",
  price: 490,
  compareAtPrice: 690,
  totalLessons,
  totalDuration,
  modules,
  includes: [
    "5 modules vidéo, 22 leçons, environ 6 heures de contenu",
    "Accès à vie, mises à jour comprises",
    "Le Kit BrandOS & Roadmap offert avec la formation",
    "Ressources téléchargeables par module (Notion, PDF, Figma)",
    "Espace membre avec suivi de progression",
    "Garantie 30 jours, sans justification",
  ],
  forWho: [
    "Tu es bon dans ton métier, mais ta marque ne raconte rien de précis",
    "Tu as déjà une activité et tu veux la rendre lisible",
    "Tu préfères un système à une inspiration",
    "Tu veux comprendre les décisions, pas juste appliquer un template",
  ],
  notForWho: [
    "Tu cherches un logo livré en 48 h — prends un designer, pas une formation",
    "Tu n’as pas encore d’offre ni de client : commence par vendre",
    "Tu veux déléguer entièrement ta marque sans y toucher",
    "Tu attends une recette de croissance sur les réseaux : ce n’est pas le sujet",
  ],
};

export function getModule(id: string): CourseModule | undefined {
  return course.modules.find((m) => m.id === id);
}

/** Progression simulée : ratio de leçons terminées. */
export function courseProgress(): { done: number; total: number; percent: number } {
  const done = course.modules.reduce(
    (n, m) => n + m.lessons.filter((l) => l.status === "done").length,
    0,
  );
  return {
    done,
    total: totalLessons,
    percent: Math.round((done / totalLessons) * 100),
  };
}
