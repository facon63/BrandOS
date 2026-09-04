import { Breadcrumbs, type Crumb } from "@/components/ui/Breadcrumbs";
import { Container } from "@/components/ui/Container";
import { Eyebrow } from "@/components/ui/Badge";
import { cx } from "@/lib/format";

/**
 * Hero standard des pages intérieures : fond sombre, fil d’Ariane, titre,
 * chapô. Toutes les pages profondes le partagent pour ne jamais perdre le
 * visiteur.
 */
export function PageHero({
  eyebrow,
  title,
  lead,
  crumbs,
  children,
  className,
}: {
  eyebrow?: string;
  title: React.ReactNode;
  lead?: React.ReactNode;
  crumbs?: Crumb[];
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        /* pt = 72 px de header fixe + respiration. */
        "on-dark relative overflow-hidden bg-obsidian pb-16 text-white",
        "pt-[calc(72px+3.5rem)] sm:pb-20 sm:pt-[calc(72px+4rem)]",
        className,
      )}
    >
      <div className="grid-lines pointer-events-none absolute inset-0" aria-hidden="true" />
      <Container className="relative">
        {crumbs && <Breadcrumbs items={crumbs} tone="dark" className="mb-8" />}
        <div className="max-w-3xl">
          {eyebrow && <Eyebrow tone="crown">{eyebrow}</Eyebrow>}
          <h1 className="mt-4 text-4xl text-white sm:text-5xl lg:text-[3.5rem]">
            {title}
          </h1>
          {lead && (
            <p className="mt-5 max-w-2xl text-lg leading-relaxed text-dark-muted">
              {lead}
            </p>
          )}
          {children && <div className="mt-8">{children}</div>}
        </div>
      </Container>
    </div>
  );
}
