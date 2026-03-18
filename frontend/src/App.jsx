import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import RoutesPage from './pages/Routes'
import RidesPage from './pages/Rides'
import BookingsPage from './pages/Bookings'
import ParcelsPage from './pages/Parcels'
import DriverMapPage from './pages/DriverMap'
import ProfitabilityPage from './pages/Profitability'
import VehiclesPage from './pages/Vehicles'
import Layout from './components/Layout'

function RequireAuth({ children }) {
  const token = localStorage.getItem('token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
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
          <Route index element={<Navigate to="/routes" replace />} />
          <Route path="routes"   element={<RoutesPage />} />
          <Route path="rides"    element={<RidesPage />} />
          <Route path="bookings" element={<BookingsPage />} />
          <Route path="parcels"     element={<ParcelsPage />} />
          <Route path="driver-map"    element={<DriverMapPage />} />
          <Route path="profitability" element={<ProfitabilityPage />} />
          <Route path="vehicles"      element={<VehiclesPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
