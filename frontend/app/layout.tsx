import type { Metadata } from "next";
import { DM_Sans, Lora } from "next/font/google";
import "./globals.css";

const sans = DM_Sans({ subsets: ["latin"], variable: "--font-sans" });
const serif = Lora({ subsets: ["latin"], variable: "--font-serif" });

export const metadata: Metadata = {
  title: "The Forecast | World Cup Match Predictor",
  description: "A World Cup machine learning predictor that updates team ratings, match forecasts, and tournament odds as results come in.",
  openGraph: {
    title: "The Forecast | World Cup Match Predictor",
    description: "Live World Cup forecasts powered by an adaptive machine learning model, Poisson match projections, and Monte Carlo tournament simulations.",
    url: "https://worldcup.ryxncodes.com",
    siteName: "The Forecast",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body className={`${sans.variable} ${serif.variable}`}>{children}</body>
    </html>
  );
}
