import { useState } from 'react'
import { Routes, Route, NavLink, Link, useLocation } from 'react-router-dom'
import {
    Home, Server, BarChart3, AlertTriangle, Layers, Terminal,
    Menu, X, Sun, Moon, ChevronDown, Plus, Trash2
} from 'lucide-react'
import { useTheme } from './context/ThemeContext'
import { useDeployments } from './context/DeploymentsContext'
import { Dashboard } from './views/Dashboard'
import { AgentsView } from './views/Agents'
import { PredictionsView } from './views/Predictions'
import { AnomaliesView } from './views/Anomalies'
import { DeploymentsView } from './views/Deployments'
import { AgentInstallView } from './views/AgentInstall'

const nav = [
    { name: 'Dashboard', href: '/', icon: Home },
    { name: 'Agents', href: '/agents', icon: Server },
    { name: 'Predictions', href: '/predictions', icon: BarChart3 },
    { name: 'Anomalies', href: '/anomalies', icon: AlertTriangle },
    { name: 'Deployments', href: '/deployments', icon: Layers },
]

function envBadge(env: string) {
    const map: Record<string, { text: string; cls: string }> = {
        production: { text: 'prod', cls: 'bg-green-500' },
        staging: { text: 'stg', cls: 'bg-yellow-500' },
        development: { text: 'dev', cls: 'bg-blue-500' },
    }
    return map[env] || { text: env, cls: 'bg-slate-500' }
}

export function App() {
    const { theme, toggle, isDark } = useTheme()
    const { deployments, current, setCurrent, remove } = useDeployments()
    const [sidebarOpen, setSidebarOpen] = useState(false)
    const [depDropdown, setDepDropdown] = useState(false)
    const location = useLocation()

    const isActive = (href: string) => href === '/' ? location.pathname === '/' : location.pathname.startsWith(href)

    return (
        <div className="min-h-screen" style={{ background: 'var(--bg-primary)', transition: 'background 0.3s ease' }}>
            {/* Mobile overlay */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Sidebar */}
            <aside
                className={`fixed inset-y-0 left-0 z-50 w-64 transform transition-transform lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
                style={{ background: 'var(--bg-primary)', borderRight: '1px solid var(--border)' }}
            >
                {/* Logo */}
                <div className="h-16 flex items-center gap-3 px-6" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--accent-gradient)' }}>
                        <span className="text-white font-bold text-sm">P</span>
                    </div>
                    <span className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>PreScale</span>
                    <span
                        className="ml-auto text-xs font-mono px-1.5 py-0.5 rounded"
                        style={{ color: 'var(--text-muted)', background: 'var(--bg-card)', border: '1px solid var(--border)' }}
                    >
                        v0.3.0
                    </span>
                </div>

                {/* Nav links */}
                <nav className="p-4 space-y-1">
                    {nav.map(item => (
                        <NavLink
                            key={item.name}
                            to={item.href}
                            onClick={() => setSidebarOpen(false)}
                            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200"
                            style={{
                                background: isActive(item.href) ? 'rgba(99,102,241,0.1)' : 'transparent',
                                color: isActive(item.href) ? 'var(--accent-400)' : 'var(--text-muted)',
                            }}
                        >
                            <item.icon className="w-5 h-5" />
                            {item.name}
                        </NavLink>
                    ))}
                    <NavLink
                        to="/install"
                        onClick={() => setSidebarOpen(false)}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200"
                        style={{
                            background: location.pathname === '/install' ? 'rgba(99,102,241,0.1)' : 'transparent',
                            color: location.pathname === '/install' ? 'var(--accent-400)' : 'var(--text-muted)',
                        }}
                    >
                        <Terminal className="w-5 h-5" />
                        Install Agent
                    </NavLink>
                </nav>
            </aside>

            {/* Main content */}
            <div className="lg:pl-64">
                {/* Top bar */}
                <header
                    className="h-16 flex items-center justify-between px-4 lg:px-6"
                    style={{ background: 'var(--bg-primary)', borderBottom: '1px solid var(--border)' }}
                >
                    <button
                        onClick={() => setSidebarOpen(true)}
                        className="lg:hidden p-2 rounded-lg transition-colors cursor-pointer"
                        style={{ color: 'var(--text-muted)' }}
                    >
                        <Menu className="w-6 h-6" />
                    </button>

                    <div className="flex-1" />

                    {/* Deployment Selector */}
                    {deployments.length > 0 && (
                        <div className="relative mr-4">
                            <button
                                onClick={() => setDepDropdown(v => !v)}
                                className="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all cursor-pointer"
                                style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                            >
                                {current && (
                                    <span className={`w-2 h-2 rounded-full ${envBadge(current.environment).cls}`} />
                                )}
                                <span className="text-sm font-medium">{current?.name || 'Select Deployment'}</span>
                                <ChevronDown className="w-4 h-4" style={{ color: 'var(--text-muted)' }} />
                            </button>

                            {depDropdown && (
                                <>
                                    <div className="fixed inset-0 z-40" onClick={() => setDepDropdown(false)} />
                                    <div
                                        className="absolute right-0 mt-1 w-64 rounded-lg shadow-2xl py-1 z-50"
                                        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                                    >
                                        {deployments.map(dep => (
                                            <div
                                                key={dep.id}
                                                className="flex items-center justify-between px-2 group transition-colors"
                                                style={{ background: current?.id === dep.id ? 'rgba(99,102,241,0.1)' : 'transparent' }}
                                            >
                                                <button
                                                    onClick={() => { setCurrent(dep.id); setDepDropdown(false) }}
                                                    className="flex-1 flex items-center gap-2 py-2 px-1 text-sm text-left truncate cursor-pointer"
                                                    style={{ color: 'var(--text-secondary)' }}
                                                >
                                                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${envBadge(dep.environment).cls}`} />
                                                    <span className="truncate">{dep.name}</span>
                                                </button>
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); if (confirm(`Delete ${dep.name}?`)) remove(dep.id) }}
                                                    className="p-1.5 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:text-red-500 cursor-pointer"
                                                    style={{ color: 'var(--text-muted)' }}
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        ))}
                                        <div style={{ borderTop: '1px solid var(--border)', margin: '0.25rem 0' }} />
                                        <Link
                                            to="/install"
                                            onClick={() => setDepDropdown(false)}
                                            className="flex items-center gap-2 px-3 py-2 text-sm"
                                            style={{ color: 'var(--accent-400)' }}
                                        >
                                            <Plus className="w-4 h-4" />
                                            Add Deployment
                                        </Link>
                                    </div>
                                </>
                            )}
                        </div>
                    )}

                    {/* Theme toggle */}
                    <button
                        onClick={toggle}
                        className="p-2 rounded-lg transition-all cursor-pointer"
                        style={{ color: 'var(--text-muted)' }}
                    >
                        {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
                    </button>
                </header>

                {/* Routes */}
                <main className="p-4 lg:p-6">
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/agents" element={<AgentsView />} />
                        <Route path="/predictions" element={<PredictionsView />} />
                        <Route path="/anomalies" element={<AnomaliesView />} />
                        <Route path="/deployments" element={<DeploymentsView />} />
                        <Route path="/install" element={<AgentInstallView />} />
                    </Routes>
                </main>
            </div>
        </div>
    )
}
