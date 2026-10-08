// Grille temporelle de l'intro, quantifiée sur la musique.
// Changer BPM ici décale toutes les scènes (l'audio lit les mêmes valeurs via audio/timing.json).

export const FPS = 30;
export const BPM = 128;
export const BEAT = 60 / BPM; // 0,46875 s
export const BAR = 4 * BEAT; // 1,875 s
export const DURATION_S = 10;
export const DURATION_FRAMES = Math.round(DURATION_S * FPS);

/** Temps (s) du temps n (n = 0 au début). */
export const beat = (n: number) => n * BEAT;
/** Frame la plus proche d'un instant en secondes. */
export const f = (seconds: number) => Math.round(seconds * FPS);

// Découpage (en temps musicaux)
export const SECTIONS = {
  hook: { from: 0, to: 1 }, // 0,00 → 0,47 s
  u1: { from: 1, to: 6 }, // 0,47 → 2,81 s
  u2: { from: 6, to: 11 }, // 2,81 → 5,16 s
  u3: { from: 11, to: 16 }, // 5,16 → 7,50 s (break sur le temps 15)
  u4: { from: 16, to: 10 / BEAT }, // 7,50 → 10,00 s (DROP sur le temps 16)
} as const;

export const DROP_S = beat(16); // 7,5 s exactement
