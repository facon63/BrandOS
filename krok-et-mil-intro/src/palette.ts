// Couleurs échantillonnées sur les références (voir CHARACTER_SHEET.md).
// Modifier ici pour changer les couleurs de tous les plans.

export const INK = '#0b0909'; // trait (contours), échantillonné #030202, légèrement relevé

export const KROK = {
  identity: '#83327F', // violet du hoodie (couleur d'identité)
  hoodie: '#83327F',
  hoodieShade: '#45194A',
  hoodieHighlight: '#A65AA0',
  drawstring: '#2A0F2B',
  skin: '#FDC292',
  skinShade: '#E1856E',
  pants: '#413D34',
  pantsShade: '#242320',
  shoes: '#3D3830',
  shoesShade: '#24211C',
  tee: '#3A3633', // t-shirt sombre visible au col
  cap: '#35322B',
  hair: '#F9CC11',
  hairShade: '#D09409',
};

export const MIL = {
  identity: '#9ABB24', // vert lime du t-shirt (couleur d'identité)
  tee: '#9ABB24',
  teeShade: '#628513',
  teeHighlight: '#C9DD4E',
  skin: '#F7CAAA',
  skinShade: '#DE9572',
  pants: '#2E3639',
  pantsShade: '#1B2123',
  shoes: '#3D3830',
  shoesShade: '#24211C',
  hair: '#583827',
  hairHighlight: '#9F866D',
  phones: '#575C5F',
  phonesDark: '#2B2F30',
  phonesLight: '#8A8788',
};

// Couleurs du logo : reprennent les hex d'identité
export const LOGO = {
  krok: KROK.identity,
  mil: MIL.identity,
  et: '#FFF6DF',
  outline: '#1a0f1c',
  shadow: 'rgba(20, 8, 24, 0.35)',
};
