
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0c",
        panel: "#15151a",
        primary: "#ec4899", // Pink
        secondary: "#8b5cf6", // Violet
        accent: "#3b82f6", // Blue
      },
    },
  },
  plugins: [],
}
