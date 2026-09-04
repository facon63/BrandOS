import type { Metadata, Viewport } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import { site } from "@/data/site";
import "./globals.css";

/* Display : géométrique bold, écho au wordmark « BrandOS ».
   Texte : sans-serif neutre, très lisible en paragraphe long. */
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  display: "swap",
  weight: ["500", "600", "700"],
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: {
    default: `${site.name} — ${site.baseline}`,
    template: `%s · ${site.name}`,
  },
  description: site.description,
  openGraph: {
    type: "website",
    locale: "fr_FR",
    siteName: site.name,
    title: `${site.name} — ${site.baseline}`,
    description: site.description,
  },
  /* TODO (phase 2) : remplacer par les PNG officiels dès qu’ils sont fournis
     (favicon16x16.png, favicon32x32.png, appletouchicon.png, androidchrome*). */
  icons: {
    icon: [{ url: "/brand/favicon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/brand/favicon.svg" }],
  },
};

export const viewport: Viewport = {
  themeColor: "#141414",
  colorScheme: "light",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" className={`${spaceGrotesk.variable} ${inter.variable}`}>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
