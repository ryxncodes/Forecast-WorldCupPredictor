"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { MenuIcon, XIcon } from "./Icons";
type Props = { simulations?: number };

type ThemeChoice = "light" | "dark";

const navLinks = [
  { href: "/", label: "Forecast" },
  { href: "/bracket", label: "Bracket" },
  { href: "/third-place", label: "Third place" },
  { href: "/history", label: "History" },
  { href: "/matches", label: "Matches" },
  { href: "/accuracy", label: "Accuracy" },
];

function getSystemTheme(): ThemeChoice {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeChoice>("light");

  useEffect(() => {
    const saved = window.localStorage.getItem("forecast-theme") as ThemeChoice | null;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = (nextTheme: ThemeChoice) => {
      document.documentElement.dataset.theme = nextTheme;
      setTheme(nextTheme);
    };
    applyTheme(saved ?? (media.matches ? "dark" : "light"));
    const listener = () => {
      if (!window.localStorage.getItem("forecast-theme")) applyTheme(getSystemTheme());
    };
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    window.localStorage.setItem("forecast-theme", nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    setTheme(nextTheme);
  }

  return <button className="theme-toggle" type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}><span aria-hidden="true">{theme === "dark" ? "☾" : "☀"}</span>{theme === "dark" ? "Dark" : "Light"}</button>;
}

export function Header({ simulations }: Props) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    document.body.classList.toggle("mobile-nav-open", menuOpen);
    return () => document.body.classList.remove("mobile-nav-open");
  }, [menuOpen]);

  const renderNavItems = () => navLinks.map((link) => (
    <Link className={pathname === link.href ? "active" : ""} href={link.href} key={link.href} onClick={() => setMenuOpen(false)}>
      {link.label}
    </Link>
  ));

  return (
    <header className="site-header">
      <button className="mobile-menu-toggle" type="button" aria-label="Open navigation menu" aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => setMenuOpen(true)}><MenuIcon /></button>
      <Link className="brand" href="/">The Forecast</Link>
      <nav className="desktop-nav" aria-label="Dashboard sections">{renderNavItems()}</nav>
      <div className="header-actions">
        {simulations ? <span className="simulation-count"><span className="auto-status-dot" />Automatically updated · {simulations.toLocaleString()} simulations</span> : null}
        <ThemeToggle />
      </div>
      {menuOpen ? <button className="mobile-drawer-backdrop" type="button" aria-label="Dismiss navigation menu" onClick={() => setMenuOpen(false)} /> : null}
      <aside className={menuOpen ? "mobile-drawer open" : "mobile-drawer"} id="mobile-navigation" aria-hidden={!menuOpen}>
        <div className="mobile-drawer-heading">
          <span>Navigation</span>
          <button type="button" aria-label="Close navigation menu" onClick={() => setMenuOpen(false)}><XIcon /></button>
        </div>
        <nav aria-label="Mobile dashboard sections">{renderNavItems()}</nav>
      </aside>
    </header>
  );
}
