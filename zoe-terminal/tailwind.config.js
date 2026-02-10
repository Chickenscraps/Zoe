/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0e0e10",
        surface: "#18181b",
        "surface-highlight": "#27272a",
        border: "#3f3f46",
        text: {
          primary: "#f5f5f5",
          secondary: "#a1a1aa",
          muted: "#71717a",
        },
        brand: {
          DEFAULT: "#f5f5f5", // White as brand
          accent: "#3f3f46",
        },
        profit: "#22c55e", // Green-500
        loss: "#ef4444",   // Red-500
        warning: "#eab308", // Yellow-500
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["Roboto Mono", "monospace"],
      },
    },
  },
  plugins: [],
}
