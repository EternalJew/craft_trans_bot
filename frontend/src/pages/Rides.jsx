import { useEffect, useState } from 'react'
import { getRides, getRoutes, createRide, deleteRide } from '../api'

const EMPTY_FORM = {
  route_id: '',
  date: '',
  seats_total: 8,
  vehicle: '',
  driver: '',
  price: '',
}

export default function RidesPage() {
  const [rides, setRides]       = useState([])
  const [routes, setRoutes]     = useState([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState(EMPTY_FORM)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const load = async () => {
    const [ridesRes, routesRes] = await Promise.all([getRides(), getRoutes()])
    setRides(ridesRes.data)
    setRoutes(routesRes.data)
  }

  useEffect(() => { load() }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await createRide({
        ...form,
        route_id: Number(form.route_id),
        seats_total: Number(form.seats_total),
        price: form.price ? Number(form.price) : null,
      })
      setShowForm(false)
      setForm(EMPTY_FORM)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Помилка збереження')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Видалити рейс? Всі бронювання також будуть видалені.')) return
    await deleteRide(id)
    load()
  }

  const statusBadge = (status) =>
    status === 'active'
      ? 'bg-green-100 text-green-700'
      : 'bg-red-100 text-red-500'

  const freePercent = (ride) =>
    Math.round(((ride.seats_total - ride.seats_free) / ride.seats_total) * 100)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Рейси</h1>
        <button
          onClick={() => { setForm(EMPTY_FORM); setError(''); setShowForm(true) }}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          + Новий рейс
        </button>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">ID</th>
              <th className="px-4 py-3 text-left">Дата</th>
              <th className="px-4 py-3 text-left">Маршрут</th>
              <th className="px-4 py-3 text-left">Транспорт</th>
              <th className="px-4 py-3 text-left">Водій</th>
              <th className="px-4 py-3 text-left">Місця</th>
              <th className="px-4 py-3 text-left">Ціна</th>
              <th className="px-4 py-3 text-left">Статус</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rides.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-8 text-gray-400">
                  Рейсів ще немає
                </td>
              </tr>
            )}
            {rides.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-400">#{r.id}</td>
                <td className="px-4 py-3 font-medium">{r.date}</td>
                <td className="px-4 py-3">
                  <div className="font-medium">{r.route?.name}</div>
                  <div className="text-xs text-gray-400">{r.route?.direction}</div>
                </td>
                <td className="px-4 py-3 text-gray-600">{r.vehicle || '—'}</td>
                <td className="px-4 py-3 text-gray-600">{r.driver || '—'}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="text-sm">
                      {r.seats_free}/{r.seats_total}
                    </div>
                    <div className="w-16 bg-gray-200 rounded-full h-1.5">
                      <div
                        className="bg-blue-500 h-1.5 rounded-full"
                        style={{ width: `${freePercent(r)}%` }}
                      />
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-600">
                  {r.price ? `${r.price} грн` : '—'}
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusBadge(r.status)}`}>
                    {r.status === 'active' ? 'Активний' : 'Скасований'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleDelete(r.id)}
                    className="text-red-400 hover:text-red-600 text-sm"
                  >
                    Видалити
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal form */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
            <div className="flex items-center justify-between p-5 border-b">
              <h2 className="text-lg font-bold">Новий рейс</h2>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-700 text-xl">✕</button>
            </div>

            <form onSubmit={handleSubmit} className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Маршрут</label>
                <select
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={form.route_id}
                  onChange={(e) => setForm({ ...form, route_id: e.target.value })}
                  required
                >
                  <option value="">— Оберіть маршрут —</option>
                  {routes.filter(r => r.is_active).map((r) => (
                    <option key={r.id} value={r.id}>{r.name} ({r.direction})</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Дата</label>
                  <input
                    type="date"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.date}
                    onChange={(e) => setForm({ ...form, date: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Кількість місць</label>
                  <input
                    type="number"
                    min="1"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.seats_total}
                    onChange={(e) => setForm({ ...form, seats_total: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Транспортний засіб</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="VW Crafter"
                    value={form.vehicle}
                    onChange={(e) => setForm({ ...form, vehicle: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Водій</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="ПІБ водія"
                    value={form.driver}
                    onChange={(e) => setForm({ ...form, driver: e.target.value })}
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Ціна (грн)</label>
                <input
                  type="number"
                  min="0"
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="1200"
                  value={form.price}
                  onChange={(e) => setForm({ ...form, price: e.target.value })}
                />
              </div>

              {error && <p className="text-red-500 text-sm">{error}</p>}

              <div className="flex gap-3 justify-end pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50"
                >
                  Скасувати
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  {loading ? 'Збереження...' : 'Створити рейс'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
