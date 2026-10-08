# BrandOS — site vitrine

Site vitrine de **BrandOS**, système d'identité de marque clé en main pour
solopreneurs. Ce dépôt couvre la **phase 1** : structure complète du site,
direction artistique, storytelling et données mockées typées.

## Stack

| Choix | Raison |
|---|---|
| **Next.js 15 (App Router) + TypeScript** | Les pages `/espace-membre`, `/panier`, `/compte` et les filtres produits demandent de l'état client et du routing dynamique. Un générateur purement statique (Astro) deviendrait un frein dès la phase 2 (paiement, authentification). |
| **Tailwind CSS v4** | Les tokens du design system sont déclarés une seule fois dans `@theme` (`app/globals.css`) et deviennent des utilitaires (`bg-crown`, `text-ink-500`, `rounded-lg`…). Pas de `tailwind.config.js` : en v4, la source de vérité est le CSS. |
| **Framer Motion** | Uniquement pour les apparitions au scroll, l'accordéon et la micro-interaction du plumage. Toutes les animations respectent `prefers-reduced-motion`. |
| Composants UI faits main | Accordéon, onglets, carrousel : quatre primitives suffisent, sans la dépendance et la surface de configuration de shadcn/ui. |

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # build de production
npm run typecheck  # tsc --noEmit
```

## Design system

Source unique : le bloc `@theme` de `app/globals.css`.

### Couleurs

| Token | Hex | Usage |
|---|---|---|
| `crown` | `#FFD600` | CTA, accents, highlights, le « OS » du wordmark |
| `obsidian` | `#141414` | Sections sombres, texte sur fond clair |
| `charcoal` | `#232323` | Footer, surfaces sombres secondaires |
| `teal` | `#3399A6` | Liens, badges, éléments graphiques |
| `pearl` | `#F0F0F2` | Cards, sections alternées claires |
| blanc | `#FFFFFF` | Surfaces |

Les tokens `ink-100` → `ink-900`, `crown-hover`, `teal-hover`, `crown-soft`,
`teal-soft` et `dark-muted` sont **dérivés** de cette palette (nuances de gris
et états hover/focus). Aucune autre teinte n'est introduite.

**Contraste** : le Crown Yellow n'est jamais utilisé comme couleur de texte sur
fond clair. Il ne sert que de fond, toujours associé à l'Obsidian Black
(bouton primaire, badges). Sur fond sombre, il sert d'accent typographique.

### Rayons, ombres, animation

- Rayons : `sm` 6px · `md` 10px · `lg` 16px · `xl` 24px
- Ombres : `soft` (surfaces au repos), `lift` (survol), `crown` (bouton primaire) — volontairement très diffuses
- Espacement : échelle Tailwind par défaut (4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96 px)
- Transitions : 200–300 ms, courbe `--ease-brand` (`cubic-bezier(.22, 1, .36, 1)`)

### Composants de base

`components/ui/` — `Button` / `ButtonLink`, `Badge`, `Eyebrow`, `Card`,
`Container`, `Section`, `SectionHeading`, `Accordion`, `Breadcrumbs`,
`ProgressBar`, `Field`, `Reveal`, `MockShot`.

`Section` porte l'alternance clair/sombre qui rythme le scroll
(`tone="white" | "pearl" | "obsidian" | "charcoal"`). Sur fond sombre, la
classe `on-dark` bascule l'anneau de focus en Crown Yellow.

## Identité

Le symbole (paon de face, plumes déployées, couronne) est **reconstruit en
SVG** : les PNG de la charte n'étaient pas fournis avec le dépôt.

- Géométrie partagée : `components/brand/peacock-geometry.ts`
- Composants : `PeacockMark` (animé) et `PeacockMarkStatic`
- Export statique : `public/brand/peacock-mark.svg`, `public/brand/favicon.svg`

Le tracé utilise `currentColor` : le symbole fonctionne tel quel en version
inversée (blanc) sur Obsidian, Charcoal ou Peacock Teal.

**Micro-interaction signature** : au repos, les plumes sont partiellement
refermées ; au survol elles se déploient en éventail, en cascade du centre vers
l'extérieur. Réservée au logo du header et au hero — nulle part ailleurs.

Pour substituer les fichiers officiels, voir `public/brand/README.md`.

## Données

Les données sont des **modules TypeScript typés**, pas des appels réseau. Le
contrat est décrit dans `lib/types.ts` ; brancher un CMS ne devrait toucher que
`data/`.

| Fichier | Contenu |
|---|---|
| `data/site.ts` | Navigation, footer, réseaux sociaux, chiffres de réassurance |
| `data/products.ts` | 5 produits digitaux |
| `data/courses.ts` | Formation : 5 modules, 22 leçons |
| `data/case-studies.ts` | 4 études de cas avec avant/après |
| `data/testimonials.ts` | 5 témoignages |
| `data/faq.ts` | 15 questions en 4 catégories |
| `data/cart.ts` | Panier de démonstration |

> Tous les contenus sont **fictifs** et destinés à valider la mise en page. Les
> chiffres de réassurance (`trustStats`), les études de cas et les témoignages
> sont à remplacer par des données réelles et vérifiables avant mise en ligne.

## Ce qui est simulé (phase 2)

Chaque simulation est signalée par un commentaire `TODO (phase 2)` dans le code
et par un bandeau visible côté interface là où l'utilisateur pourrait s'y
tromper.

| Fonctionnalité | Fichier | À brancher sur |
|---|---|---|
| Ajout au panier | `components/products/AddToCartButton.tsx` | État de panier persistant |
| Paiement | `components/cart/CartSummary.tsx` | Stripe Checkout |
| Connexion / inscription | `components/account/AuthPanel.tsx` | Auth.js, Clerk ou Supabase |
| Progression de formation | `components/course/MemberPortal.tsx` | Progression réelle de l'utilisateur |
| Lecteur vidéo | `components/course/VideoPlayerMock.tsx` | Mux, Vimeo ou équivalent |
| Newsletter | `components/layout/NewsletterForm.tsx` | Brevo, Loops… |
| Formulaire de contact | `components/marketing/ContactForm.tsx` | Server Action + envoi transactionnel |
| Captures produit | `components/ui/MockShot.tsx` | Vraies captures d'écran |
| Visuels avant/après | `components/cases/BrandBoard.tsx` | Vraies captures client |

## Pages

```
/                          Accueil (hero, problème, 3 piliers, produit phare,
                           preuve, témoignages, FAQ courte, CTA)
/produits                  Catalogue filtrable par type
/produits/[slug]           Fiche produit
/formation                 Page de vente longue
/formation/programme       Programme détaillé, leçon par leçon
/espace-membre             Portail post-achat (mock)
/etudes-de-cas             Liste filtrable par secteur
/etudes-de-cas/[slug]      Étude détaillée + comparateur avant/après
/a-propos                  Manifeste, valeurs, histoire
/tarifs                    Comparatif des trois offres
/faq                       FAQ catégorisée
/contact                   Formulaire (mock)
/panier                    Panier (mock)
/compte                    Connexion / inscription (mock)
```

## Parcours pris en compte

1. **Le curieux** — Accueil → étude de cas → produit ou formation → fiche → panier
2. **Le pressé** — Accueil → nav « Produits » → fiche → ajout au panier
3. **L'investisseur** — `/formation` (page longue) → FAQ formation → `/tarifs` → `/espace-membre`
4. **Le client existant** — `/compte` → `/espace-membre` → reprise de la progression

Header et footer sont identiques partout ; toutes les pages profondes portent un
fil d'Ariane.

## Accessibilité

- Lien d'évitement vers le contenu principal
- Un seul `<h1>` par page, hiérarchie de titres respectée
- Accordéon, onglets et carrousel pilotés au clavier, avec `aria-expanded`,
  `aria-controls`, `aria-selected` et régions `aria-live`
- Comparateur avant/après construit sur un `<input type="range">` natif
- Anneau de focus visible partout, adapté au fond (Peacock Teal / Crown Yellow)
- `prefers-reduced-motion` neutralise animations et défilement fluide
- Tableau comparatif avec `<caption>`, `scope="col"` / `scope="row"` et
  équivalents textuels pour les pictogrammes inclus/non inclus

## Responsive

Mobile-first, vérifié à 390 px, 768 px et 1440 px sur les 15 routes : aucun
débordement horizontal. Le tableau comparatif défile dans son propre conteneur
plutôt que d'écraser la page. La navigation mobile est un menu plein écran.

## Autre outil du dépôt : KrokCut

Le dossier [`krokcut/`](krokcut/README.md) contient une application indépendante (Python) de dérush et de
montage automatiques pour la chaîne YouTube Krok et Mil : synchronisation de deux POV, transcription,
sélection des moments par Claude, montage (zooms, bruitages, personnages) et export Premiere/DaVinci.
Elle n'a aucun lien avec le site Next.js.
