# Assets de marque BrandOS

## Ce qui est présent
- `peacock-mark.svg` — symbole paon couronné en line-art, **reconstruit en SVG**
  (les PNG originaux n'étaient pas fournis avec le dépôt). Il est également
  disponible en composant React animable : `components/brand/PeacockMark.tsx`.
- `favicon.svg` — favicon vectoriel dérivé du symbole.

## À remplacer quand les fichiers officiels sont disponibles
Déposer ici les fichiers listés dans la charte, puis mettre à jour
`app/layout.tsx` (bloc `icons`) et `components/brand/Logo.tsx` :

| Fichier attendu               | Usage                                  |
|-------------------------------|----------------------------------------|
| `primarylockuporiginal.png`   | Lockup principal (fond clair)          |
| `favicon16x16.png`            | Favicon 16                             |
| `favicon32x32.png`            | Favicon 32                             |
| `appletouchicon.png`          | Apple touch icon (180×180)             |
| `androidchrome192x192.png`    | PWA 192                                |
| `androidchrome512x512.png`    | PWA 512                                |

Le symbole est dessiné avec `stroke="currentColor"` dans le composant React :
il fonctionne donc tel quel en version inversée (blanc) sur Obsidian Black,
Charcoal ou Peacock Teal, conformément aux tests de la charte.
