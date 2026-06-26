import { ImageResponse } from "next/og";

export const alt = "The Forecast World Cup 2026 predictor";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          alignItems: "stretch",
          background: "#08111d",
          color: "#edf4f7",
          display: "flex",
          flexDirection: "column",
          fontFamily: "Arial, sans-serif",
          height: "100%",
          justifyContent: "space-between",
          padding: "70px",
          width: "100%",
        }}
      >
        <div style={{ alignItems: "center", display: "flex", gap: "20px" }}>
          <div
            style={{
              alignItems: "center",
              border: "3px solid #61d39b",
              borderRadius: "18px",
              display: "flex",
              fontSize: "28px",
              fontWeight: 800,
              height: "72px",
              justifyContent: "center",
              width: "72px",
            }}
          >
            TF
          </div>
          <span style={{ color: "#9eabb8", fontSize: "32px", fontWeight: 700 }}>The Forecast</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "28px", maxWidth: "940px" }}>
          <h1 style={{ fontSize: "82px", letterSpacing: "-3px", lineHeight: 1.02, margin: 0 }}>
            World Cup 2026 predictor
          </h1>
          <p style={{ color: "#c8d2dc", fontSize: "34px", lineHeight: 1.35, margin: 0 }}>
            Live team ratings, match forecasts, bracket odds, and model accuracy tracking.
          </p>
        </div>
        <div style={{ alignItems: "center", color: "#61d39b", display: "flex", fontSize: "28px", fontWeight: 800, gap: "18px" }}>
          <span>worldcup.ryxncodes.com</span>
          <span style={{ color: "#ff9c89" }}>10,000 simulations</span>
        </div>
      </div>
    ),
    size,
  );
}
