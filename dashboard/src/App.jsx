import { Routes, Route } from 'react-router-dom'
import Layout from './layout/Layout'
import Supervision from './pages/Supervision'
import Documentation from './pages/Documentation'
import Assistant from './pages/Assistant'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Supervision />} />
        <Route path="/docs" element={<Documentation />} />
        <Route path="/assistant" element={<Assistant />} />
      </Route>
    </Routes>
  )
}