import type { BrandSnapshot } from "@/lib/types";
import { cx } from "@/lib/format";

/* ============================================================================
   TODO (phase 2) — remplacer par de vraies captures avant/après du client.
   En attendant, on reconstruit une « planche de marque » à partir de la
   palette et de la typo décrites dans les données : c’est plus honnête qu’une
   photo générique, et cela montre exactement ce qui a changé.
   ========================================================================= */

export function BrandBoard({
  snapshot,
  client,
  variant,
  className,
  dense = false,
}: {
  snapshot: BrandSnapshot;
  client: string;
  variant: "before" | "after";
  className?: string;
  /** Vignette : on retire le nom et la typo, redondants avec la card. */
  dense?: boolean;
}) {
  const [c1, c2, c3, c4] = snapshot.palette;

  return (
    <div
      className={cx(
        "relative flex aspect-[4/3] flex-col justify-between overflow-hidden rounded-lg border border-ink-200",
        dense ? "p-4" : "p-6",
        className,
      )}
      style={{ background: variant === "before" ? c3 : c3 }}
    >
      {/* Bloc-titre : simule le lockup du client. */}
      <div>
        <span
          className="inline-block rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]"
          style={{ background: c1, color: c3 }}
        >
          {snapshot.label}
        </span>

        {!dense && (
          <>
            <p
              className={cx(
                "mt-5 text-2xl leading-tight sm:text-3xl",
                variant === "before"
                  ? "font-serif italic"
                  : "font-display font-bold tracking-[-0.03em]",
              )}
              style={{ color: c1 }}
            >
              {client}
            </p>

            <p className="mt-1.5 text-[12px]" style={{ color: c4 }}>
              {snapshot.typeface}
            </p>
          </>
        )}
      </div>

      {/* Bandes de couleur : l’identité, réduite à ses aplats. */}
      <div>
        {variant === "before" ? (
          /* Avant : couleurs dispersées, tailles inégales — l’incohérence. */
          <div className="flex h-12 items-end gap-1.5">
            {snapshot.palette.map((hex, i) => (
              <span
                key={hex + i}
                className="rounded-[4px] border border-black/5"
                style={{
                  background: hex,
                  width: `${[34, 22, 28, 16][i] ?? 20}%`,
                  height: `${[100, 62, 80, 45][i] ?? 60}%`,
                }}
              />
            ))}
          </div>
        ) : (
          /* Après : un système régulier. */
          <div className="grid h-12 grid-cols-4 gap-1.5">
            {snapshot.palette.map((hex, i) => (
              <span
                key={hex + i}
                className="rounded-[4px] border border-black/5"
                style={{ background: hex }}
              />
            ))}
          </div>
        )}

        <div className="mt-3 flex items-center gap-2">
          <span
            className="h-1 flex-1 rounded-full"
            style={{ background: variant === "before" ? c4 : c2 }}
          />
          {!dense && (
            <span
              className="font-display text-[10px] font-semibold uppercase tracking-[0.12em]"
              style={{ color: c4 }}
            >
              {variant === "before" ? "Sans règles" : "Système documenté"}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/** Liste d’observations affichée sous une planche. */
export function BoardNotes({
  snapshot,
  variant,
}: {
  snapshot: BrandSnapshot;
  variant: "before" | "after";
}) {
  return (
    <ul className="mt-4 flex flex-col gap-2">
      {snapshot.notes.map((note) => (
        <li key={note} className="flex gap-2.5 text-[14px] leading-snug text-ink-600">
          <span
            aria-hidden="true"
            className={cx(
              "mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full",
              variant === "before" ? "bg-ink-300" : "bg-teal",
            )}
          />
          {note}
        </li>
      ))}
    </ul>
  );
}
