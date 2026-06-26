import type { Metadata } from "next";
import { DM_Sans, Lora } from "next/font/google";
import "./globals.css";

const sans = DM_Sans({ subsets: ["latin"], variable: "--font-sans" });
const serif = Lora({ subsets: ["latin"], variable: "--font-serif" });

export const metadata: Metadata = {
  metadataBase: new URL("https://worldcup.ryxncodes.com"),
  title: "The Forecast | World Cup Match Predictor",
  description: "A World Cup machine learning predictor that updates team ratings, match forecasts, and tournament odds as results come in.",
  applicationName: "The Forecast",
  icons: {
    icon: [
      { url: "/favicon-32.png?v=3", sizes: "32x32", type: "image/png" },
      { url: "/icon-192.png?v=3", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png?v=3", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png?v=3", sizes: "180x180", type: "image/png" }],
  },
  openGraph: {
    title: "The Forecast | World Cup Match Predictor",
    description: "Live World Cup forecasts powered by an adaptive machine learning model, Poisson match projections, and Monte Carlo tournament simulations.",
    url: "https://worldcup.ryxncodes.com",
    siteName: "The Forecast",
    images: [
      {
        url: "/og-worldcup.png?v=3",
        width: 1200,
        height: 630,
        alt: "The Forecast World Cup 2026 predictor",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "The Forecast | World Cup Match Predictor",
    description: "Live World Cup forecasts powered by an adaptive model and tournament simulations.",
    images: ["/og-worldcup.png?v=3"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body className={`${sans.variable} ${serif.variable}`}>{children}</body>
    </html>
  );
}
