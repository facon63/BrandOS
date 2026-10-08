import { Config } from '@remotion/cli/config';

Config.setVideoImageFormat('png');
Config.setConcurrency(4);
// Navigateur headless : variable d'environnement REMOTION_BROWSER (sinon Remotion télécharge le sien).
if (process.env.REMOTION_BROWSER) {
  Config.setBrowserExecutable(process.env.REMOTION_BROWSER);
}
