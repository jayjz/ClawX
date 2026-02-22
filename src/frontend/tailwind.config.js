/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    fontFamily: {
      sans: ['Inter', 'SF Pro Display', 'system-ui', 'sans-serif'],
      mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', '"Courier New"', 'Monaco', 'Menlo', 'monospace'],
    },
    extend: {
      colors: {
        // ── 2026 Premium Pivot palette ──────────────────────────────
        'oled-black':   '#0A0A0A',   // root / deepest backgrounds
        'titan-grey':   '#1F1F1F',   // panel / card backgrounds
        'titan-border': '#2A2A2A',   // borders, dividers
        'accent-green': '#00FF9F',   // primary accent (alive, profit, confirm)
        'accent-amber': '#FF9500',   // warning (wagers, idle, caution)
        'accent-red':   '#FF3B30',   // death, loss, errors
        'accent-cyan':  '#00F0FF',   // research, markets, info
        // ── Legacy tokens (retained for backwards compat only) ──────
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
        // Landing page animations
        'float': 'float 6s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'ticker-scroll': 'ticker-scroll 40s linear infinite',
        'marquee':        'marquee 28s linear infinite',
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
        // Landing page keyframes
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-12px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'ticker-scroll': {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
        'marquee': {
          '0%':   { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-33.333%)' },
        },
      },
    },
  },
  plugins: [],
}
