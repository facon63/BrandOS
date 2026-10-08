import { loadFont } from '@remotion/fonts';
import { staticFile } from 'remotion';

// Polices libres embarquées (public/fonts) : Luckiest Guy (Apache 2.0) pour le logo, Bangers (OFL) pour les onomatopées,
// Fredoka (OFL) pour les minuscules arrondies (« et », bulle « ouf »).
export const LOGO_FONT = 'Luckiest Guy';
export const COMIC_FONT = 'Bangers';
export const ROUND_FONT = 'Fredoka';

loadFont({ family: LOGO_FONT, url: staticFile('fonts/LuckiestGuy-Regular.ttf') });
loadFont({ family: COMIC_FONT, url: staticFile('fonts/Bangers-Regular.ttf') });
loadFont({ family: ROUND_FONT, url: staticFile('fonts/Fredoka.ttf'), weight: '300 700' });
