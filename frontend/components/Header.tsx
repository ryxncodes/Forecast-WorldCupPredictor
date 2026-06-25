"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
type Props = { simulations?: number };

type ThemeChoice = "light" | "dark";

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
  return (
    <header className="site-header">
      <Link className="brand" href="/">The Forecast</Link>
      <nav aria-label="Dashboard sections">
        <Link className={pathname === "/" ? "active" : ""} href="/">Forecast</Link>
        <Link className={pathname === "/third-place" ? "active" : ""} href="/third-place">Third place</Link>
        <Link className={pathname === "/history" ? "active" : ""} href="/history">History</Link>
        <Link className={pathname === "/matches" ? "active" : ""} href="/matches">Matches</Link>
      </nav>
      <div className="header-actions">
        {simulations ? <span className="simulation-count"><span className="auto-status-dot" />Automatically updated · {simulations.toLocaleString()} simulations</span> : null}
        <ThemeToggle />
      </div>
    </header>
  );
}
