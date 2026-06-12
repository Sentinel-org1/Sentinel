// tailwind.config.js - ESM format to match package.json "type": "module"
export default {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#c084fc', // Vibrant lavender/purple
        secondary: '#22d3ee', // Glowing ice cyan
        slate: {
          50: '#faf9fc',
          100: '#f4f1f8',
          200: '#e7e0f2',
          300: '#d5c6e8',
          400: '#baa3da',
          450: '#a387c9', // Sage-lavender custom shade
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#150f24', // Deep obsidian dark purple border
          850: '#0e0a1b', // Card bg deep purple
          900: '#0a0614', // Sidebar bg ultra dark purple
          950: '#05030a', // Main dashboard bg pitch-black purple
        },
        blue: {
          50: '#fff1f2',
          100: '#ffe4e6',
          200: '#fecdd3',
          300: '#fda4af',
          400: '#fb7185', // Coral pink for highlights
          450: '#f43f5e', // Hot pink for blue-450 text/links
          500: '#e11d48', // Electric rose for blue-500
          600: '#be123c',
          700: '#9f1239',
          800: '#881337',
          900: '#4c0519',
          950: '#27040f',
        },
        indigo: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6', // Electric violet for indigo-500
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
          950: '#2e1065',
        },
        emerald: {
          450: '#34d399', // Mint green
        },
        amber: {
          450: '#fbbf24', // Rich gold
        },
        rose: {
          450: '#f43f5e', // Hot rose
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      keyframes: {
        'pulse-crimson': {
          '0%, 100%': { borderColor: 'rgba(244, 63, 94, 0.25)', boxShadow: '0 0 12px rgba(244, 63, 94, 0.1)' },
          '50%': { borderColor: 'rgba(244, 63, 94, 0.7)', boxShadow: '0 0 25px rgba(244, 63, 94, 0.35)' },
        },
      },
      animation: {
        'pulse-crimson': 'pulse-crimson 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
};
