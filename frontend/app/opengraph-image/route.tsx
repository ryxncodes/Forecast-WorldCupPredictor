import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

export const dynamic = "force-static";

const size = {
  width: 1200,
  height: 630,
};

async function backgroundDataUrl() {
  const image = await readFile(join(process.cwd(), "public", "og-worldcup.png"));
  return `data:image/png;base64,${image.toString("base64")}`;
}

export async function GET() {
  const background = await backgroundDataUrl();

  return new ImageResponse(
    (
      <div
        style={{
          background: "#08111d",
          color: "#edf4f7",
          display: "flex",
          fontFamily: "Arial, sans-serif",
          height: "100%",
          overflow: "hidden",
          position: "relative",
          width: "100%",
        }}
      >
        <img
          alt=""
          src={background}
          style={{
            height: "100%",
            left: 0,
            objectFit: "cover",
            position: "absolute",
            top: 0,
            width: "100%",
          }}
        />
        <div
          style={{
            background: "linear-gradient(90deg, rgba(8,17,29,0.08) 0%, rgba(8,17,29,0.72) 42%, rgba(8,17,29,0.97) 100%)",
            bottom: 0,
            left: 0,
            position: "absolute",
            right: 0,
            top: 0,
          }}
        />
        <div
          style={{
            bottom: 62,
            display: "flex",
            flexDirection: "column",
            position: "absolute",
            right: 68,
            top: 66,
            width: 505,
          }}
        >
          <div style={{ color: "#61d39b", display: "flex", fontSize: 27, fontWeight: 800, letterSpacing: 1.2, textTransform: "uppercase" }}>
            The Forecast
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 22,
              justifyContent: "center",
              minHeight: 380,
            }}
          >
            <h1
              style={{
                color: "#ffffff",
                fontSize: 76,
                fontWeight: 900,
                letterSpacing: -2.8,
                lineHeight: 0.98,
                margin: 0,
              }}
            >
              World Cup 2026 predictor
            </h1>
            <p
              style={{
                color: "#d3dde6",
                fontSize: 31,
                fontWeight: 500,
                lineHeight: 1.28,
                margin: 0,
              }}
            >
              Live match forecasts, bracket odds, and model accuracy tracking.
            </p>
          </div>
          <div
            style={{
              alignItems: "center",
              borderTop: "1px solid rgba(211,221,230,0.25)",
              color: "#ff9c89",
              display: "flex",
              fontSize: 25,
              fontWeight: 800,
              marginTop: "auto",
              paddingTop: 24,
            }}
          >
            worldcup.ryxncodes.com
          </div>
        </div>
      </div>
    ),
    size,
  );
}
