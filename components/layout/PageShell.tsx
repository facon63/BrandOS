import { Header } from "./Header";
import { Footer } from "./Footer";

/**
 * Enveloppe commune à toutes les pages : header sticky + contenu + footer.
 *
 * Le header est en `position: fixed` et transparent tant qu’on n’a pas
 * scrollé : c’est donc la première section de la page qui fournit le fond
 * derrière lui. Toute page dont la première section est sombre passe
 * `headerTone="dark"` **et** réserve elle-même les 72 px du header
 * (`PageHero` et les heros maison le font via `pt-[72px]`).
 *
 * `offsetHeader` n’est utile que pour les pages sans hero dédié (404, pages
 * d’erreur) : il ajoute le décalage à la place.
 */
export function PageShell({
  children,
  headerTone = "light",
  offsetHeader = false,
}: {
  children: React.ReactNode;
  headerTone?: "light" | "dark";
  offsetHeader?: boolean;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <Header tone={headerTone} />
      <main id="contenu" className={offsetHeader ? "flex-1 pt-[72px]" : "flex-1"}>
        {children}
      </main>
      <Footer />
    </div>
  );
}
