import { useEffect, useState } from 'react'

export default function App() {
  const [me, setMe] = useState<any>(null)
  useEffect(() => {
    fetch('/api/whoami').then(r => r.json()).then(setMe).catch(() => {})
  }, [])
  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 720, margin: '24px auto' }}>
      <h1>Cowork React + FastAPI Monorepo</h1>
      <p>Cowork sub-app skeleton is live. 后端在 <code>backend/app.py</code>，前端在 <code>frontend/src/</code>。</p>
      <pre>{JSON.stringify(me, null, 2)}</pre>
    </div>
  )
}
