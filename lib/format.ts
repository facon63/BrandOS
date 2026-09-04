/** Formatage des prix en euros, sans décimales inutiles. */
export function formatPrice(value: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/** 384 → « 6 h 24 ». Utilisé pour les durées de formation. */
export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h} h`;
  return `${h} h ${String(m).padStart(2, "0")}`;
}

/** 14 → « 14 min », pour les leçons individuelles. */
export function formatLessonDuration(minutes: number): string {
  return `${minutes} min`;
}

/** Concatène des classes conditionnelles sans dépendance externe. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
