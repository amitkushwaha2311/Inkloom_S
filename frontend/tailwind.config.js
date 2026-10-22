/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        obsidian: '#191916',
        charcoal: '#252520',
        ivory: '#F4F0E8',
        'paper-white': '#FBF9F4',
        copper: '#B96B49',
        'copper-highlight': '#D79570',
        chartreuse: '#C5CF78',
        'secondary-text': '#77766E',
        'surface-dark': '#20201C',
        'surface-secondary': '#292923',
        border: 'rgba(37,37,32,0.12)',
        'border-dark': 'rgba(244,240,232,0.12)',
      },
      fontFamily: {
        sans: ['"Helvetica Neue Light"', 'Helvetica', 'Arial', 'Inter', 'sans-serif'],
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
        body: ['Barlow', 'sans-serif'],
        display: ['"Playfair Display"', 'Georgia', 'serif'],
        oswald: ['Oswald', 'sans-serif'],
        montserrat: ['Montserrat', 'sans-serif'],
        'roboto-slab': ['"Roboto Slab"', 'serif'],
        raleway: ['Raleway', 'sans-serif'],
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-down': {
          '0%': { opacity: '0', transform: 'translateY(-12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) both',
        'fade-down': 'fade-down 0.7s cubic-bezier(0.16, 1, 0.3, 1) both',
      },
    },
  },
  plugins: [],
}
