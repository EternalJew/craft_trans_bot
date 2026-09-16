import { useEffect, useState } from 'react'
import { createBooking, getRoute } from '../api'

const fmtDate = (iso) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('uk-UA', { weekday: 'short', day: 'numeric', month: 'long' })

const EMPTY = {
  direction: 'UA->CZ', ride_id: '', from_city: '', to_city: '', name: '', phone: '',
  seats: 1, from_address: '', to_address: '', comment: '',
}

const DIRECTIONS = [
  { value: 'UA->CZ', label: '🇺🇦 → 🇨🇿  Україна → Чехія' },
  { value: 'CZ->UA', label: '🇨🇿 → 🇺🇦  Чехія → Україна' },
]

// Typing in a booking taken over the phone. It goes down the same path as a
// website booking: into the queue, and to the owner's Telegram to be copied
// into the book.
export default function CallForm({ rides, onSaved }) {
  const [form, setForm]     = useState(EMPTY)
  const [stops, setStops]   = useState({ pickup: [], dropoff: [] })
  const [saving, setSaving] = useState(false)
  const [note, setNote]     = useState(null)

  const today = new Date().toISOString().slice(0, 10)
  // Direction first, then the dates that direction actually runs on — so the
  // nearest departure the other way is never quietly preselected.
  const upcoming = rides
    .filter((r) => r.status === 'active' && r.date >= today && r.route.direction === form.direction)
    .sort((a, b) => a.date.localeCompare(b.date))

  useEffect(() => {
    if (upcoming.length && !upcoming.some((r) => String(r.id) === String(form.ride_id))) {
      set('ride_id', upcoming[0].id)
    }
  }, [form.direction, upcoming.length])

  useEffect(() => {
    const ride = upcoming.find((r) => String(r.id) === String(form.ride_id))
    if (!ride) return
    getRoute(ride.route_id).then((res) => setStops({
      pickup:  res.data.stops.filter((s) => s.pickup).map((s) => s.city),
      dropoff: res.data.stops.filter((s) => s.dropoff).map((s) => s.city),
    }))
  }, [form.ride_id])

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }))

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setNote(null)
    try {
      const res = await createBooking({
        ride_id: Number(form.ride_id),
        name: form.name.trim(),
        phone: form.phone.trim(),
        seats: Number(form.seats),
        from_city: form.from_city.trim(),
        to_city: form.to_city.trim(),
        from_address: form.from_address.trim() || null,
        to_address: form.to_address.trim() || null,
        comment: form.comment.trim() || null,
        source: 'admin',
      })
      setNote({ ok: true, text: `№${res.data.id} записано — батьку надіслано в Telegram.` })
      setForm({ ...EMPTY, direction: form.direction, ride_id: form.ride_id })
      onSaved?.()
    } catch (err) {
      setNote({ ok: false, text: err.response?.data?.detail || 'Не вдалося зберегти' })
    } finally {
      setSaving(false)
    }
  }

  const field = 'border rounded-lg px-3 py-2 w-full'

  return (
    <form onSubmit={submit} className="bg-white rounded-lg shadow-sm p-4 mb-8">
      <div className="font-semibold mb-3">📞 Записати дзвінок</div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <select value={form.direction} onChange={(e) => set('direction', e.target.value)} className={field}>
          {DIRECTIONS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
        <select value={form.ride_id} onChange={(e) => set('ride_id', e.target.value)} className={`${field} md:col-span-2`} required>
          {upcoming.map((r) => (
            <option key={r.id} value={r.id}>{fmtDate(r.date)}</option>
          ))}
        </select>

        <input list="call-from" value={form.from_city} onChange={(e) => set('from_city', e.target.value)}
               placeholder="Звідки (місто або село)" className={field} required autoComplete="off" />
        <datalist id="call-from">{stops.pickup.map((c) => <option key={c} value={c} />)}</datalist>

        <input list="call-to" value={form.to_city} onChange={(e) => set('to_city', e.target.value)}
               placeholder="Куди" className={field} required autoComplete="off" />
        <datalist id="call-to">{stops.dropoff.map((c) => <option key={c} value={c} />)}</datalist>

        <input type="number" min="1" max="8" value={form.seats} onChange={(e) => set('seats', e.target.value)}
               className={field} required title="Місць" />

        <input value={form.name} onChange={(e) => set('name', e.target.value)}
               placeholder="Ім'я" className={field} required />
        <input value={form.phone} onChange={(e) => set('phone', e.target.value)}
               placeholder="Телефон" className={field} required type="tel" />
        <input value={form.comment} onChange={(e) => set('comment', e.target.value)}
               placeholder="Коментар (багаж, дитина…)" className={field} />

        <input value={form.from_address} onChange={(e) => set('from_address', e.target.value)}
               placeholder="Адреса подачі" className={field} />
        <input value={form.to_address} onChange={(e) => set('to_address', e.target.value)}
               placeholder="Адреса висадки" className={field} />
        <button disabled={saving}
                className="bg-blue-700 hover:bg-blue-800 disabled:opacity-50 text-white rounded-lg px-4 py-2">
          {saving ? 'Зберігаю…' : 'Записати'}
        </button>
      </div>

      {note && (
        <div className={`mt-3 text-sm rounded-lg px-3 py-2 ${note.ok ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-700'}`}>
          {note.text}
        </div>
      )}
    </form>
  )
}
