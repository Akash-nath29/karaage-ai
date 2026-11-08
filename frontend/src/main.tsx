import { Analytics, type BeforeSend } from '@vercel/analytics/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Invite, reset and verify links carry secret tokens (/invite/:token, ?token=): they never leave for analytics.
const scrub: BeforeSend = (e) => ({ ...e, url: e.url.replace(/[?#].*$/, '').replace(/\/invite\/[^/]+/, '/invite/[token]') })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <Analytics mode={import.meta.env.PROD ? 'production' : 'development'} beforeSend={scrub} />
  </StrictMode>,
)
