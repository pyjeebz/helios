import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './App'
import { ThemeProvider } from './context/ThemeContext'
import { DeploymentsProvider } from './context/DeploymentsContext'
import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <BrowserRouter>
            <ThemeProvider>
                <DeploymentsProvider>
                    <App />
                </DeploymentsProvider>
            </ThemeProvider>
        </BrowserRouter>
    </React.StrictMode>
)
