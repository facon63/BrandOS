import Link from "next/link";
import { cx } from "@/lib/format";
import { PeacockMark, PeacockMarkStatic } from "./PeacockMark";

/**
 * Lockup BrandOS : symbole + wordmark.
 * « Brand » porte le fondement, « OS » passe en Crown Yellow pour marquer le
 * système. Sur fond sombre, le symbole et « Brand » passent en blanc.
 *
 * TODO (phase 2) : si `primarylockuporiginal.png` est fourni, remplacer le
 * rendu vectoriel par <Image> tout en gardant l’API de ce composant.
 */
export function Logo({
  tone = "light",
  className,
  markClassName,
  href = "/",
  animated = true,
  showWordmark = true,
}: {
  tone?: "light" | "dark";
  className?: string;
  markClassName?: string;
  href?: string | null;
  animated?: boolean;
  showWordmark?: boolean;
}) {
  /* La variante statique n’a pas de prop `deployed` : on ne la passe qu’à
     la version animée. */
  const markProps = animated ? { deployed: false } : {};
  const Mark = animated ? PeacockMark : PeacockMarkStatic;

  const content = (
    <span className={cx("group inline-flex items-center gap-2.5", className)}>
      <Mark
        compact
        {...markProps}
        strokeWidth={4}
        className={cx(
          "h-8 w-auto shrink-0",
          tone === "dark" ? "text-white" : "text-obsidian",
          markClassName,
        )}
      />
      {showWordmark && (
        <span
          className={cx(
            "font-display text-[21px] font-bold leading-none tracking-[-0.035em]",
            tone === "dark" ? "text-white" : "text-obsidian",
          )}
        >
          Brand<span className="text-crown">OS</span>
        </span>
      )}
    </span>
  );

  if (!href) return content;

  return (
    <Link href={href} aria-label="BrandOS — retour à l’accueil" className="inline-flex">
      {content}
    </Link>
  );
}
