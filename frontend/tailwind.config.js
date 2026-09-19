/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4fc",
          100: "#d7e6f8",
          500: "#2a78d6",
          600: "#2266ba",
          700: "#1c5cab",
        },
      },
    },
  },
  plugins: [],
};
