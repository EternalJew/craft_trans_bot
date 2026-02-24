import { useEffect, useState } from 'react'
import { getRoutes, createRoute, updateRoute, deleteRoute, getRoute } from '../api'
import StopEditor from '../components/StopEditor'

const EMPTY_FORM = { name: '', direction: 'UA->CZ', is_active: true, stops: [] }

export default function RoutesPage() {
  const [routes, setRoutes]     = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId]     = useState(null)
  const [form, setForm]         = useState(EMPTY_FORM)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const load = async () => {
    const res = await getRoutes()
    setRoutes(res.data)
  }

  useEffect(() => { load() }, [])

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setEditId(null)
    setError('')
    setShowForm(true)
  }

  const openEdit = async (id) => {
    const res = await getRoute(id)
    const r = res.data
    setForm({ name: r.name, direction: r.direction, is_active: r.is_active, stops: r.stops })
    setEditId(id)
    setError('')
    setShowForm(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (editId) {
        await updateRoute(editId, form)
      } else {
        await createRoute(form)
      }
      setShowForm(false)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Помилка збереження')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Видалити маршрут? Всі пов\'язані рейси також будуть видалені.')) return
    await deleteRoute(id)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Маршрути</h1>
        <button
          onClick={openCreate}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          + Новий маршрут
        </button>
      </div>

      {/* Route list */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">ID</th>
              <th className="px-4 py-3 text-left">Назва</th>
              <th className="px-4 py-3 text-left">Напрямок</th>
              <th className="px-4 py-3 text-left">Зупинки</th>
              <th className="px-4 py-3 text-left">Статус</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {routes.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-8 text-gray-400">
                  Маршрутів ще немає. Створіть перший!
                </td>
              </tr>
            )}
            {routes.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-400">#{r.id}</td>
                <td className="px-4 py-3 font-medium">{r.name}</td>
                <td className="px-4 py-3">
                  <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-medium">
                    {r.direction}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {r.stops.map((s) => s.city).join(' → ')}
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${r.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {r.is_active ? 'Активний' : 'Неактивний'}
                  </span>
                </td>
                <td className="px-4 py-3 flex gap-2 justify-end">
                  <button onClick={() => openEdit(r.id)} className="text-blue-500 hover:text-blue-700 text-sm">
                    Редагувати
                  </button>
                  <button onClick={() => handleDelete(r.id)} className="text-red-400 hover:text-red-600 text-sm">
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
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b">
              <h2 className="text-lg font-bold">{editId ? 'Редагувати маршрут' : 'Новий маршрут'}</h2>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-700 text-xl">✕</button>
            </div>

            <form onSubmit={handleSubmit} className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Назва маршруту</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Київ → Прага"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Напрямок</label>
                  <select
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.direction}
                    onChange={(e) => setForm({ ...form, direction: e.target.value })}
                  >
                    <option value="UA->CZ">UA → CZ</option>
                    <option value="CZ->UA">CZ → UA</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                <label htmlFor="is_active" className="text-sm text-gray-700">Маршрут активний</label>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Зупинки маршруту</label>
                <StopEditor
                  stops={form.stops}
                  onChange={(stops) => setForm({ ...form, stops })}
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
                  {loading ? 'Збереження...' : 'Зберегти'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
