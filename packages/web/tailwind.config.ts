import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "nev-blue": "#0066FF",
        "nev-green": "#00C896",
      },
      fontFamily: {
        sans: [
          "-apple-system", "BlinkMacSystemFont",
          "PingFang SC", "Microsoft YaHei",
          "Helvetica Neue", "Arial", "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
