import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { changePassword, logoutEverywhere } from '../api'

// The session lives a month so nobody is thrown out on a departure day.
// This page is the way to end it early: a new password, or "sign out
// everywhere" after leaving the dashboard open on someone else's computer.
export default function AccountPage() {
  const [current, setCurrent] = useState('')
  const [next, setNext]       = useState('')
  const [again, setAgain]     = useState('')
  const [message, setMessage] = useState('')
  const [error, setError]     = useState('')
  const [busy, setBusy]       = useState(false)
  const navigate = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setMessage('')
    if (next !== again) { setError('Новий пароль введено по-різному'); return }
    if (next.length < 8) { setError('Пароль має бути не коротший за 8 символів'); return }
    setBusy(true)
    try {
      const res = await changePassword(current, next)
      // the old token just died; keep this session on the new one
      localStorage.setItem('token', res.data.access_token)
      setCurrent(''); setNext(''); setAgain('')
      setMessage('Пароль змінено. Усі інші сесії завершено.')
    } catch (err) {
      setError(err.response?.data?.detail || 'Не вдалося змінити пароль')
    } finally {
      setBusy(false)
    }
  }

  const signOutAll = async () => {
    if (!confirm('Завершити всі сесії, включно з цією?')) return
    try { await logoutEverywhere() } catch { /* the token may already be dead — either way we leave */ }
    localStorage.removeItem('token')
    navigate('/login')
  }

  const input = 'w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500'

  return (
    <div className="max-w-md">
      <h1 className="text-2xl font-bold mb-6">Акаунт</h1>

      <form onSubmit={submit} className="bg-white rounded-xl shadow p-6 space-y-4">
        <h2 className="font-semibold">Змінити пароль</h2>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Поточний пароль</label>
          <input type="password" className={input} value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Новий пароль</label>
          <input type="password" className={input} value={next} onChange={(e) => setNext(e.target.value)} required autoComplete="new-password" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Ще раз</label>
          <input type="password" className={input} value={again} onChange={(e) => setAgain(e.target.value)} required autoComplete="new-password" />
        </div>
        {error && <p className="text-red-500 text-sm">{error}</p>}
        {message && <p className="text-green-600 text-sm">{message}</p>}
        <button type="submit" disabled={busy}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
          {busy ? 'Зберігаю…' : 'Зберегти'}
        </button>
      </form>

      <div className="bg-white rounded-xl shadow p-6 mt-6">
        <h2 className="font-semibold mb-1">Вийти всюди</h2>
        <p className="text-sm text-gray-500 mb-4">
          Якщо адмінка лишилась відкритою на чужому комп'ютері чи телефоні — це завершить усі сесії одразу.
        </p>
        <button onClick={signOutAll}
          className="border border-red-300 text-red-600 hover:bg-red-50 px-4 py-2 rounded-lg text-sm font-medium">
          Завершити всі сесії
        </button>
      </div>
    </div>
  )
}
