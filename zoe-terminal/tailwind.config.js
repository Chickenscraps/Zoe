/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0b0c0f", // bg-0
        surface: "#0f1116",    // bg-1
        "surface-base": "#141823", // bg-2
        "surface-highlight": "#1a2030", // bg-3
        border: "rgba(255,255,255,0.08)",
        "border-strong": "rgba(255,255,255,0.14)",
        text: {
          primary: "#f3f4f6",
          secondary: "rgba(243,244,246,0.72)",
          muted: "rgba(243,244,246,0.56)",
        },
        brand: "#f3f4f6",
        profit: "#2ee59d",
        loss: "#ff5b6e",
        warning: "#fbbf24",
      },
      boxShadow: {
        soft: "0 10px 30px rgba(0,0,0,0.35)",
        crisp: "inset 0 1px 0 rgba(255,255,255,0.06)",
      },
      borderRadius: {
        cards: "20px",
        btns: "14px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["Roboto Mono", "monospace"],
      },
    },
  },
  plugins: [],
}
