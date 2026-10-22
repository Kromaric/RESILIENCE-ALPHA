import { Routes, Route } from 'react-router-dom'
import Layout from './layout/Layout'
import RequireAuth from './auth/RequireAuth'
import Login from './pages/Login'
import Supervision from './pages/Supervision'
import Documentation from './pages/Documentation'
import Assistant from './pages/Assistant'
import Habilitations from './pages/Habilitations'
import RequireRole from './auth/RequireRole'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Supervision />} />
          <Route path="/docs/*" element={<Documentation />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route element={<RequireRole role="admin" />}>
            <Route path="/habilitations" element={<Habilitations />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  )
}
