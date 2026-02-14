/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    fontFamily: {
      mono: ['"Courier New"', 'Monaco', 'Menlo', 'monospace'],
    },
    extend: {
      colors: {
        'terminal-black': '#050505',
        'terminal-deep': '#0a0a0a',
        'terminal-surface': '#111111',
        'terminal-border': '#1a1a1a',
        'neon-green': '#00ff41',
        'neon-green-dim': '#00cc33',
        'alert-red': '#ff3333',
        'alert-red-dim': '#cc2222',
        'neon-cyan': '#00d4ff',
        'neon-amber': '#ffaa00',
        'grid-line': '#333333',
      },
      animation: {
        progress: 'progress 3s infinite linear',
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scanline': 'scanline 8s linear infinite',
        'blink': 'blink 1s steps(1) infinite',
        'flicker': 'flicker 0.15s infinite',
      },
      keyframes: {
        progress: {
          '0%': { width: '0%' },
          '100%': { width: '100%' },
        },
        scanline: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        flicker: {
          '0%': { opacity: '0.97' },
          '5%': { opacity: '0.9' },
          '10%': { opacity: '0.98' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
