import type { HandKind } from './parts';

/**
 * Pose d'un personnage. Angles en degrés : 0 = membre vers le bas, + = vers la droite de l'écran.
 * A = côté gauche de l'écran, B = côté droit de l'écran.
 */
export type Pose = {
  hipA: number;
  kneeA: number;
  hipB: number;
  kneeB: number;
  footA: number;
  footB: number;
  shA: number;
  elA: number;
  shB: number;
  elB: number;
  handA: HandKind;
  handB: HandKind;
  lean: number; // rotation du buste autour des hanches
  bob: number; // décalage vertical du haut du corps (négatif = vers le haut)
  head: number; // inclinaison de la tête
  squash: number; // 1 = neutre ; <1 écrasé ; >1 étiré (autour du point au sol)
};

export const STAND: Pose = {
  hipA: 2,
  kneeA: -1,
  hipB: -2,
  kneeB: 1,
  footA: 0,
  footB: 0,
  shA: 4,
  elA: -2,
  shB: 3,
  elB: 2,
  handA: 'relaxed',
  handB: 'relaxed',
  lean: 0,
  bob: 0,
  head: 0,
  squash: 1,
};

export const pose = (p: Partial<Pose>): Pose => ({ ...STAND, ...p });

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** Interpolation entre deux poses (les mains prennent celles de la pose la plus proche). */
export const mixPose = (a: Pose, b: Pose, t: number): Pose => {
  const out = { ...a } as Pose;
  (Object.keys(a) as (keyof Pose)[]).forEach((k) => {
    const va = a[k];
    const vb = b[k];
    if (typeof va === 'number' && typeof vb === 'number') {
      (out as Record<string, unknown>)[k] = lerp(va, vb, t);
    } else {
      (out as Record<string, unknown>)[k] = t < 0.5 ? va : vb;
    }
  });
  return out;
};

/** Cycle de course (vue de face / 3/4) — phase en tours (0..1). */
export const runCycle = (phase: number, amp = 1): Pose => {
  const s = Math.sin(phase * Math.PI * 2);
  const c = Math.cos(phase * Math.PI * 2);
  return pose({
    hipA: 18 * s * amp,
    kneeA: -Math.max(0, 40 * c * amp) - 6,
    hipB: -18 * s * amp,
    kneeB: -Math.max(0, -40 * c * amp) - 6,
    footA: 10 * s * amp,
    footB: -10 * s * amp,
    shA: 25 - 30 * s * amp,
    elA: -55,
    shB: -25 - 30 * s * amp,
    elB: 55,
    handA: 'fist',
    handB: 'fist',
    lean: 0,
    bob: -6 * Math.abs(c) * amp,
    head: 2 * s,
  });
};
