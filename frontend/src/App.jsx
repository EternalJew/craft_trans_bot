import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import BookQueuePage from './pages/BookQueue'
import BookScanPage from './pages/BookScan'
import ParcelsPage from './pages/Parcels'
import VehiclesPage from './pages/Vehicles'
import DriversPage from './pages/Drivers'
import Layout from './components/Layout'

function RequireAuth({ children }) {
  const token = localStorage.getItem('token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter basename="/admin">
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/book-queue" replace />} />
          <Route path="book-queue" element={<BookQueuePage />} />
          <Route path="book-scan"  element={<BookScanPage />} />
          <Route path="parcels"     element={<ParcelsPage />} />
          <Route path="vehicles"      element={<VehiclesPage />} />
          <Route path="drivers"       element={<DriversPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
