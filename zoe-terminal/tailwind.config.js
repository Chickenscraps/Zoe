/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#FAF3F6",
        surface: "#EFE3D3",
        "surface-base": "#F5EDE0",
        "surface-highlight": "#E8D9C5",
        border: "rgba(69, 43, 39, 0.15)",
        "border-strong": "rgba(69, 43, 39, 0.28)",
        text: {
          primary: "#301E30",
          secondary: "rgba(48, 30, 48, 0.72)",
          muted: "rgba(48, 30, 48, 0.50)",
          dim: "rgba(48, 30, 48, 0.30)",
        },
        sakura: {
          300: "#FABBC2",
          500: "#EFA3A8",
          700: "#D4787E",
        },
        earth: {
          700: "#452B27",
        },
        night: {
          800: "#363252",
          900: "#301E30",
        },
        mist: {
          500: "#6B8BB5",
        },
        cream: {
          100: "#FAF3F6",
        },
        paper: {
          100: "#EFE3D3",
        },
        brand: "#301E30",
        profit: "#4A8C5C",
        loss: "#C0392B",
        warning: "#D4A017",
        accent: "#6B8BB5",
      },
      boxShadow: {
        /* Pixel shadows: no blur, crisp offsets */
        pixel: "3px 3px 0 rgba(69, 43, 39, 0.18)",
        "pixel-sm": "2px 2px 0 rgba(69, 43, 39, 0.14)",
        "pixel-lg": "4px 4px 0 rgba(69, 43, 39, 0.22)",
        "pixel-inset": "inset 1px 1px 0 rgba(255, 255, 255, 0.45), inset -1px -1px 0 rgba(69, 43, 39, 0.10)",
        "pixel-pressed": "inset 2px 2px 0 rgba(69, 43, 39, 0.20)",
        none: "none",
      },
      borderRadius: {
        pixel: "0px",
        cards: "0px",
        btns: "0px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["Roboto Mono", "monospace"],
        pixel: ['"Press Start 2P"', "monospace"],
      },
      fontSize: {
        /* KPI display sizes */
        "kpi-lg": ["2.25rem", { lineHeight: "1.1", fontWeight: "800" }],
        "kpi-md": ["1.75rem", { lineHeight: "1.2", fontWeight: "700" }],
        "kpi-sm": ["1.25rem", { lineHeight: "1.3", fontWeight: "600" }],
      },
    },
  },
  plugins: [],
}
