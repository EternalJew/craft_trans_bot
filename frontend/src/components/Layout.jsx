import { NavLink, Outlet, useNavigate } from 'react-router-dom'

const links = [
  { to: '/routes',     label: 'Маршрути',   icon: '🗺️' },
  { to: '/rides',      label: 'Рейси',      icon: '🚐' },
  { to: '/bookings',   label: 'Бронювання', icon: '🎫' },
  { to: '/parcels',    label: 'Посилки',    icon: '📦' },
  { to: '/driver-map',    label: 'Навігація',      icon: '🧭' },
  { to: '/profitability', label: 'Рентабельність', icon: '💰' },
  { to: '/vehicles',      label: 'Автопарк',       icon: '🚐' },
]

export default function Layout() {
  const navigate = useNavigate()

  const logout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-56 bg-blue-700 text-white flex flex-col">
        <div className="px-5 py-4 text-xl font-bold border-b border-blue-600">
          CraftTrans
        </div>
        <nav className="flex-1 py-4">
          {links.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-3 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-900 text-white'
                    : 'text-blue-100 hover:bg-blue-600'
                }`
              }
            >
              <span>{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>
        <button
          onClick={logout}
          className="m-4 py-2 rounded bg-blue-900 hover:bg-blue-800 text-sm"
        >
          Вийти
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6 bg-gray-50">
        <Outlet />
      </main>
    </div>
  )
}
