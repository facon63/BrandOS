import data from '../timeline.json';

// Minutage partagé avec l'audio (audio/compose.py lit le même fichier).
export const TL = data;
export const BPM: number = data.bpm;
export const BEAT = 60 / BPM;
export const FPS: number = data.fps;
export const DURATION: number = data.duration;
export const DURATION_FRAMES = Math.round(DURATION * FPS);

/** Début (s) de chaque section. */
export const SEC = {
  hook: data.sections.hook * BEAT,
  u1: data.sections.u1 * BEAT,
  u2: data.sections.u2 * BEAT,
  u3: data.sections.u3 * BEAT,
  brk: data.sections.break * BEAT,
  u4: data.sections.u4 * BEAT,
};
export const DROP = SEC.u4;

type Ev = { name: string; beat: number; offset?: number };
const events = data.events as Ev[];

/** Instant global (s) d'un événement nommé de timeline.json. */
export const ev = (name: string): number => {
  const e = events.find((x) => x.name === name);
  if (!e) throw new Error(`événement inconnu : ${name}`);
  return e.beat * BEAT + (e.offset ?? 0);
};
