import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

type Theme = 'dark' | 'light'

interface ThemeContextValue {
    theme: Theme
    toggle: () => void
    isDark: boolean
}

const ThemeContext = createContext<ThemeContextValue>({
    theme: 'dark',
    toggle: () => { },
    isDark: true,
})

export function ThemeProvider({ children }: { children: ReactNode }) {
    const [theme, setTheme] = useState<Theme>(() => {
        const saved = localStorage.getItem('prescale-theme') as Theme
        return saved || 'dark'
    })

    useEffect(() => {
        document.documentElement.className = theme
        localStorage.setItem('prescale-theme', theme)
    }, [theme])

    const toggle = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))

    return (
        <ThemeContext.Provider value={{ theme, toggle, isDark: theme === 'dark' }}>
            {children}
        </ThemeContext.Provider>
    )
}

export const useTheme = () => useContext(ThemeContext)
