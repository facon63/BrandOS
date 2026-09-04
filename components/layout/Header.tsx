"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Logo } from "@/components/brand/Logo";
import { ButtonLink } from "@/components/ui/Button";
import { mainNav } from "@/data/site";
import { cx } from "@/lib/format";

/**
 * Header sticky. Transparent au-dessus du pli (le hero porte alors le fond),
 * puis fond blanc + hairline dès que l’on scrolle.
 *
 * `tone="dark"` est passé par les pages dont le hero est sombre : le logo et
 * les liens passent en blanc tant que le header est transparent.
 */
export function Header({ tone = "light" }: { tone?: "light" | "dark" }) {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = usePathname();
  const reduced = useReducedMotion();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  /* Ferme le menu à chaque navigation. */
  useEffect(() => setMenuOpen(false), [pathname]);

  /* Bloque le scroll de fond quand le menu plein écran est ouvert. */
  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  const onDark = tone === "dark" && !scrolled;

  return (
    <>
      <a
        href="#contenu"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-md focus:bg-obsidian focus:px-4 focus:py-2 focus:text-white"
      >
        Aller au contenu
      </a>

      <header
        className={cx(
          "fixed inset-x-0 top-0 z-50 transition-all duration-300 ease-[--ease-brand]",
          scrolled
            ? "border-b border-ink-200 bg-white/90 backdrop-blur-md"
            : "border-b border-transparent",
          onDark && "on-dark",
        )}
      >
        <div className="mx-auto flex h-[72px] max-w-6xl items-center gap-6 px-5 sm:px-8">
          <Logo tone={onDark ? "dark" : "light"} />

          <nav aria-label="Navigation principale" className="ml-4 hidden lg:block">
            <ul className="flex items-center gap-1">
              {mainNav.map((item) => {
                const active =
                  pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cx(
                        "relative rounded-md px-3 py-2 text-[15px] font-medium transition-colors",
                        onDark
                          ? "text-white/75 hover:text-white"
                          : "text-ink-600 hover:text-ink-900",
                        active && (onDark ? "text-white" : "text-ink-900"),
                      )}
                    >
                      {item.label}
                      {active && (
                        <span
                          aria-hidden="true"
                          className="absolute inset-x-3 -bottom-0.5 h-[2px] rounded-full bg-crown"
                        />
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            <IconLink
              href="/compte"
              label="Mon compte"
              onDark={onDark}
              className="hidden sm:inline-flex"
            >
              <path d="M10 10a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
              <path d="M3.5 17.5a6.5 6.5 0 0 1 13 0" />
            </IconLink>

            <IconLink href="/panier" label="Panier" onDark={onDark} badge={2}>
              <path d="M3 4h2l1.6 8.2a1.5 1.5 0 0 0 1.5 1.2h6.3a1.5 1.5 0 0 0 1.5-1.2L17 7H6" />
              <circle cx="8.5" cy="16.5" r="1" />
              <circle cx="14.5" cy="16.5" r="1" />
            </IconLink>

            {/* La visibilité responsive porte sur un conteneur : `hidden` dans
                le className du bouton entrerait en conflit avec le `inline-flex`
                de sa classe de base. */}
            <span className="hidden md:inline-flex">
              <ButtonLink href="/tarifs" size="sm">
                Rejoindre BrandOS
              </ButtonLink>
            </span>

            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              aria-label="Ouvrir le menu"
              aria-expanded={menuOpen}
              className={cx(
                "grid h-10 w-10 place-items-center rounded-md transition-colors lg:hidden",
                onDark ? "text-white hover:bg-white/10" : "text-ink-900 hover:bg-ink-100",
              )}
            >
              <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <path d="M3 6h14M3 10h14M3 14h14" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            className="fixed inset-0 z-[55] bg-obsidian on-dark lg:hidden"
            initial={reduced ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduced ? undefined : { opacity: 0 }}
            transition={{ duration: 0.22 }}
          >
            <div className="flex h-[72px] items-center px-5 sm:px-8">
              <Logo tone="dark" animated={false} />
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                aria-label="Fermer le menu"
                className="ml-auto grid h-10 w-10 place-items-center rounded-md text-white hover:bg-white/10"
              >
                <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                  <path d="M5 5l10 10M15 5L5 15" />
                </svg>
              </button>
            </div>

            <nav aria-label="Navigation mobile" className="px-5 pt-6 sm:px-8">
              <ul className="flex flex-col">
                {mainNav.map((item, i) => (
                  <motion.li
                    key={item.href}
                    initial={reduced ? false : { opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 + i * 0.05, duration: 0.35 }}
                    className="border-b border-white/10"
                  >
                    <Link
                      href={item.href}
                      className="block py-4 font-display text-2xl font-bold tracking-[-0.02em] text-white"
                    >
                      {item.label}
                    </Link>
                  </motion.li>
                ))}
              </ul>

              <div className="mt-8 flex flex-col gap-3">
                <ButtonLink href="/tarifs" size="lg">
                  Rejoindre BrandOS
                </ButtonLink>
                <ButtonLink href="/compte" variant="secondary-dark" size="lg">
                  Mon compte
                </ButtonLink>
              </div>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function IconLink({
  href,
  label,
  children,
  onDark,
  badge,
  className,
}: {
  href: string;
  label: string;
  children: React.ReactNode;
  onDark: boolean;
  badge?: number;
  className?: string;
}) {
  return (
    <Link
      href={href}
      aria-label={badge ? `${label} — ${badge} articles` : label}
      className={cx(
        "relative grid h-10 w-10 place-items-center rounded-md transition-colors",
        onDark ? "text-white hover:bg-white/10" : "text-ink-700 hover:bg-ink-100",
        className,
      )}
    >
      <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {children}
      </svg>
      {badge ? (
        <span className="absolute right-1.5 top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-crown px-1 font-display text-[10px] font-bold text-obsidian">
          {badge}
        </span>
      ) : null}
    </Link>
  );
}
