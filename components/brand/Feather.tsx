import {
  FEATHER_BARBS,
  FEATHER_BLADE,
  FEATHER_EYE,
  FEATHER_IRIS,
  FEATHER_PUPIL,
  FEATHER_RACHIS,
} from "./peacock-geometry";

/**
 * Une plume, dessinée à l'origine et pointant vers le haut.
 * Trois niveaux de détail : le filigrane de fond n'a pas besoin des barbes,
 * et à 32 px l'œil se réduit à un point.
 */
export function Feather({
  detail = "full",
  filled = false,
}: {
  detail?: "full" | "simple" | "silhouette";
  /** Lame pleine (logo sur aplat) plutôt qu'au trait. */
  filled?: boolean;
}) {
  return (
    <>
      <path
        d={FEATHER_BLADE}
        fill={filled ? "currentColor" : "none"}
        strokeWidth={filled ? 0 : undefined}
      />

      {detail !== "silhouette" && (
        <>
          <path d={FEATHER_RACHIS} fill="none" />
          {detail === "full" &&
            FEATHER_BARBS.map((d) => <path key={d} d={d} fill="none" />)}
        </>
      )}

      {/* L'œil : toujours en négatif sur une lame pleine. */}
      <ellipse
        {...FEATHER_EYE}
        fill={filled ? "var(--feather-void, #fff)" : "none"}
      />
      {detail !== "silhouette" && <ellipse {...FEATHER_IRIS} fill="none" />}
      <circle {...FEATHER_PUPIL} fill="currentColor" strokeWidth={0} />
    </>
  );
}
