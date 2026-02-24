import { useEffect, useState } from 'react'
import { getParcels, createParcel, updateParcelStatus, deleteParcel } from '../api'

const EMPTY_FORM = {
  direction: 'UA->CZ',
  sender: '',
  sender_phone: '',
  receiver: '',
  receiver_phone: '',
  np_office: '',
  description: '',
}

const STATUS_LABELS = {
  pending:    { label: 'Очікує',     color: 'bg-yellow-100 text-yellow-700' },
  in_transit: { label: 'В дорозі',   color: 'bg-blue-100 text-blue-700' },
  delivered:  { label: 'Доставлено', color: 'bg-green-100 text-green-700' },
}

export default function ParcelsPage() {
  const [parcels, setParcels]   = useState([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState(EMPTY_FORM)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const load = async () => {
    const res = await getParcels()
    setParcels(res.data)
  }

  useEffect(() => { load() }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await createParcel(form)
      setShowForm(false)
      setForm(EMPTY_FORM)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Помилка збереження')
    } finally {
      setLoading(false)
    }
  }

  const handleStatusChange = async (id, status) => {
    await updateParcelStatus(id, status)
    load()
  }

  const handleDelete = async (id) => {
    if (!confirm('Видалити посилку?')) return
    await deleteParcel(id)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Посилки</h1>
        <button
          onClick={() => { setForm(EMPTY_FORM); setError(''); setShowForm(true) }}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          + Нова посилка
        </button>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">ID</th>
              <th className="px-4 py-3 text-left">Напрямок</th>
              <th className="px-4 py-3 text-left">Відправник</th>
              <th className="px-4 py-3 text-left">Отримувач</th>
              <th className="px-4 py-3 text-left">НП офіс</th>
              <th className="px-4 py-3 text-left">Опис</th>
              <th className="px-4 py-3 text-left">Дата</th>
              <th className="px-4 py-3 text-left">Статус</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {parcels.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-8 text-gray-400">
                  Посилок ще немає
                </td>
              </tr>
            )}
            {parcels.map((p) => (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-400">#{p.id}</td>
                <td className="px-4 py-3">
                  <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-medium">
                    {p.direction}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium">{p.sender}</div>
                  <div className="text-xs text-gray-400">{p.sender_phone}</div>
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium">{p.receiver}</div>
                  <div className="text-xs text-gray-400">{p.receiver_phone}</div>
                </td>
                <td className="px-4 py-3 text-gray-600">{p.np_office}</td>
                <td className="px-4 py-3 text-gray-500 max-w-xs truncate">{p.description || '—'}</td>
                <td className="px-4 py-3 text-gray-400 text-xs">
                  {new Date(p.created_at).toLocaleDateString('uk-UA')}
                </td>
                <td className="px-4 py-3">
                  <select
                    className={`text-xs font-medium rounded px-2 py-1 border-0 focus:outline-none cursor-pointer ${STATUS_LABELS[p.status]?.color}`}
                    value={p.status}
                    onChange={(e) => handleStatusChange(p.id, e.target.value)}
                  >
                    <option value="pending">Очікує</option>
                    <option value="in_transit">В дорозі</option>
                    <option value="delivered">Доставлено</option>
                  </select>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleDelete(p.id)}
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
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b">
              <h2 className="text-lg font-bold">Нова посилка</h2>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-700 text-xl">✕</button>
            </div>

            <form onSubmit={handleSubmit} className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Напрямок</label>
                <select
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  value={form.direction}
                  onChange={(e) => setForm({ ...form, direction: e.target.value })}
                >
                  <option value="UA->CZ">UA → CZ</option>
                  <option value="CZ->UA">CZ → UA</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Відправник (ПІБ)</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.sender}
                    onChange={(e) => setForm({ ...form, sender: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Телефон відправника</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="+380XXXXXXXXX"
                    value={form.sender_phone}
                    onChange={(e) => setForm({ ...form, sender_phone: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Отримувач (ПІБ)</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.receiver}
                    onChange={(e) => setForm({ ...form, receiver: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Телефон отримувача</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="+380XXXXXXXXX"
                    value={form.receiver_phone}
                    onChange={(e) => setForm({ ...form, receiver_phone: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Відділення Нової Пошти</label>
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Відділення №5, м. Київ"
                  value={form.np_office}
                  onChange={(e) => setForm({ ...form, np_office: e.target.value })}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Опис вантажу</label>
                <textarea
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3}
                  placeholder="Що веземо?"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
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
