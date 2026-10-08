// Petites fonctions d'animation (temps en secondes).

export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
/** Progression normalisée de t entre a et b (bornée 0..1). */
export const seg = (t: number, a: number, b: number) => clamp((t - a) / (b - a));

export const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
export const easeOut = (x: number) => 1 - Math.pow(1 - x, 3);
export const easeIn = (x: number) => x * x * x;
export const easeOutBack = (x: number, k = 1.70158) => 1 + (k + 1) * Math.pow(x - 1, 3) + k * Math.pow(x - 1, 2);

/** Saut parabolique : hauteur (>= 0) entre t0 et t1, sommet h. */
export const hop = (t: number, t0: number, t1: number, h: number) => {
  if (t <= t0 || t >= t1) return 0;
  const u = (t - t0) / (t1 - t0);
  return 4 * h * u * (1 - u);
};

/** Apparition « pop » avec dépassement (0 -> 1,15 -> 1) sur `d` secondes. */
export const popIn = (t: number, t0: number, d = 0.25) => {
  const u = seg(t, t0, t0 + d);
  return u <= 0 ? 0 : easeOutBack(u, 2.2);
};

/** Ressort amorti autour de 0 après t0 (pour squash & stretch). */
export const wobble = (t: number, t0: number, amp = 0.2, freq = 14, damp = 7) => {
  if (t < t0) return 0;
  const u = t - t0;
  return amp * Math.exp(-damp * u) * Math.sin(u * freq);
};

/** Interpolation par images clés : [[t, v], ...] avec lissage easeInOut entre les clés. */
export const keys = (t: number, k: [number, number][], ease: (x: number) => number = easeInOut) => {
  if (t <= k[0][0]) return k[0][1];
  for (let i = 0; i < k.length - 1; i++) {
    const [t0, v0] = k[i];
    const [t1, v1] = k[i + 1];
    if (t <= t1) return lerp(v0, v1, ease((t - t0) / (t1 - t0)));
  }
  return k[k.length - 1][1];
};

/** Pseudo-aléatoire déterministe. */
export const rnd = (i: number) => {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};
