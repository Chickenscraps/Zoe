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
        soft: "0 4px 12px rgba(69, 43, 39, 0.10)",
        crisp: "inset 0 1px 0 rgba(255, 255, 255, 0.5)",
      },
      borderRadius: {
        cards: "4px",
        btns: "4px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["Roboto Mono", "monospace"],
        pixel: ['"Press Start 2P"', "monospace"],
      },
    },
  },
  plugins: [],
}
