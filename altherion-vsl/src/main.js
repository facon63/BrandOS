// Point d'entrée : charge polices, images et timeline, puis expose le rendu.
// - Aperçu navigateur : lecture synchronisée avec le mixage audio (../out/mix.wav)
// - Rendu : ?render=1 → window.__render(t) est appelé image par image par tools/render.mjs
import { createFilm } from './scenes.js';

const params = new URLSearchParams(location.search);
const RENDER = params.has('render');
const MODE = params.get('founder') === 'avatar' ? 'avatar' : 'photo';
if (RENDER) document.body.classList.add('render');

const loadImg = (src) => new Promise((res, rej) => {
  const i = new Image();
  i.onload = () => res(i);
  i.onerror = rej;
  i.src = src;
});

async function boot() {
  const faces = [
    '300 40px "Cormorant Garamond"', '400 40px "Cormorant Garamond"', 'italic 400 40px "Cormorant Garamond"',
    '500 40px "Cormorant Garamond"', '600 40px "Cormorant Garamond"', '400 20px Manrope', '500 20px Manrope',
    '600 20px Manrope', '700 20px Manrope', '400 20px "JetBrains Mono"', '500 20px "JetBrains Mono"',
  ];
  await Promise.all(faces.map((f) => document.fonts.load(f, 'AÉÂàz09')));
  const [TL, founder, glow, avatar] = await Promise.all([
    fetch('timeline.json').then((r) => r.json()),
    // la photo n'est pas versionnée (règles d'anonymat) : sans elle, on bascule sur l'avatar
    loadImg('../assets/img/founder_graded.png').catch(() => null),
    loadImg('../assets/img/founder_glow.png'),
    loadImg('../assets/img/founder_avatar.png'),
  ]);
  const film = createFilm({ TL, images: { founder, glow, avatar }, mode: founder ? MODE : 'avatar' });
  const canvas = document.getElementById('c');
  const ctx = canvas.getContext('2d');
  window.__render = (t) => film.render(ctx, t);
  window.__events = () => film.events;
  window.__duration = film.duration;
  window.__ready = true;
  if (RENDER) return;

  // ---- aperçu interactif
  const audio = new Audio('../out/mix.wav');
  const seek = document.getElementById('seek');
  const tc = document.getElementById('tc');
  const btn = document.getElementById('play');
  seek.max = film.duration;
  let t = Number(params.get('t') || 0);
  audio.currentTime = t;
  btn.onclick = () => (audio.paused ? audio.play() : audio.pause());
  audio.onplay = () => (btn.textContent = 'PAUSE');
  audio.onpause = () => (btn.textContent = 'LECTURE');
  seek.oninput = () => { t = Number(seek.value); audio.currentTime = t; };
  const loop = () => {
    if (!audio.paused) t = audio.currentTime;
    film.render(ctx, t);
    seek.value = t;
    tc.textContent = t.toFixed(2);
    requestAnimationFrame(loop);
  };
  loop();
}
boot().catch((e) => { document.body.textContent = String(e); console.error(e); });
