import { useEffect, useState } from 'react'
import { getUsers, createUser, updateUser, deleteUser } from '../api'

const EMPTY_FORM = {
  username: '',
  password: '',
  full_name: '',
  phone: '',
  telegram_id: '',
  role: 'driver',
}

export default function DriversPage() {
  const [users, setUsers]       = useState([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState(EMPTY_FORM)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const load = async () => setUsers((await getUsers()).data)

  useEffect(() => { load() }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await createUser({
        ...form,
        telegram_id: form.telegram_id ? Number(form.telegram_id) : null,
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

  const handleTelegramId = async (user) => {
    const value = prompt(
      `Telegram ID для ${user.full_name || user.username}.\n` +
      'Водій може дізнатись свій ID у бота @userinfobot.',
      user.telegram_id || '',
    )
    if (value === null) return
    await updateUser(user.id, { telegram_id: value ? Number(value) : null })
    load()
  }

  const handleDelete = async (user) => {
    if (!confirm(`Видалити ${user.username}?`)) return
    await deleteUser(user.id)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Водії</h1>
        <button
          onClick={() => { setForm(EMPTY_FORM); setError(''); setShowForm(true) }}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          + Новий водій
        </button>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        Без Telegram ID водій не зможе відкрити маніфест у Telegram — саме за цим ID
        його впізнає застосунок.
      </p>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">Логін</th>
              <th className="px-4 py-3 text-left">ПІБ</th>
              <th className="px-4 py-3 text-left">Телефон</th>
              <th className="px-4 py-3 text-left">Роль</th>
              <th className="px-4 py-3 text-left">Telegram ID</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {users.length === 0 && (
              <tr><td colSpan={6} className="text-center py-8 text-gray-400">Користувачів ще немає</td></tr>
            )}
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{u.username}</td>
                <td className="px-4 py-3 text-gray-600">{u.full_name || '—'}</td>
                <td className="px-4 py-3 text-gray-600">{u.phone || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                  }`}>
                    {u.role === 'admin' ? 'Адмін' : 'Водій'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {u.telegram_id
                    ? <span className="font-mono text-xs">{u.telegram_id}</span>
                    : <span className="text-orange-500 text-xs">не вказано</span>}
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  <button onClick={() => handleTelegramId(u)} className="text-blue-500 hover:text-blue-700 text-sm mr-4">
                    Telegram ID
                  </button>
                  <button onClick={() => handleDelete(u)} className="text-red-400 hover:text-red-600 text-sm">
                    Видалити
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
            <div className="flex items-center justify-between p-5 border-b">
              <h2 className="text-lg font-bold">Новий водій</h2>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-700 text-xl">✕</button>
            </div>

            <form onSubmit={handleSubmit} className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Логін</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={form.username}
                    onChange={(e) => setForm({ ...form, username: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
                  <input
                    type="password"
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">ПІБ</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Телефон</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    placeholder="+380..."
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Telegram ID</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    placeholder="123456789"
                    value={form.telegram_id}
                    onChange={(e) => setForm({ ...form, telegram_id: e.target.value })}
                  />
                  <p className="text-xs text-gray-400 mt-1">Дізнатись: @userinfobot</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Роль</label>
                  <select
                    className="w-full border rounded-lg px-3 py-2 text-sm"
                    value={form.role}
                    onChange={(e) => setForm({ ...form, role: e.target.value })}
                  >
                    <option value="driver">Водій</option>
                    <option value="admin">Адмін</option>
                  </select>
                </div>
              </div>

              {error && <p className="text-red-500 text-sm">{error}</p>}

              <div className="flex gap-3 justify-end pt-2">
                <button type="button" onClick={() => setShowForm(false)}
                        className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50">
                  Скасувати
                </button>
                <button type="submit" disabled={loading}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                  {loading ? 'Збереження...' : 'Створити'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
