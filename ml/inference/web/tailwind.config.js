/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
                mono: ['DM Mono', 'monospace'],
            },
            animation: {
                'pulse-slow': 'pulse 2s ease-in-out infinite',
            },
        },
    },
    plugins: [],
}
