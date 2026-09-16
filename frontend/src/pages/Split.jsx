import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getRides, getRideBookings, getRideSplit, saveRideSplit } from '../api'

const fmtDate = (iso) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('uk-UA', { weekday: 'short', day: 'numeric', month: 'long' })

// A day's passengers laid out as vans. The proposal groups by corridor;
// the person who knows the roads moves whoever it got wrong, then saves.
export default function SplitPage() {
  const [params, setParams] = useSearchParams()
  const [rides, setRides]       = useState([])
  const [rideId, setRideId]     = useState(params.get('ride') || '')
  const [bookings, setBookings] = useState({})
  const [vans, setVans]         = useState([])
  const [capacity, setCapacity] = useState(8)
  const [saved, setSaved]       = useState(false)
  const [busy, setBusy]         = useState(false)
  const [note, setNote]         = useState(null)
  const [suggested, setSuggested] = useState(null)

  useEffect(() => { getRides().then((r) => setRides(r.data)) }, [])

  useEffect(() => {
    if (!rideId) return
    setParams({ ride: rideId })
    setBusy(true); setNote(null)
    Promise.all([getRideBookings(rideId), getRideSplit(rideId)]).then(([b, s]) => {
      setBookings(Object.fromEntries(b.data.map((x) => [x.id, x])))
      setVans(s.data.vans)
      setCapacity(s.data.capacity)
      setSaved(s.data.saved)
      setSuggested(s.data.suggested_vans)
    }).finally(() => setBusy(false))
  }, [rideId])

  const ride = rides.find((r) => String(r.id) === String(rideId))

  const proposeFor = async (n) => {
    setBusy(true); setNote(null)
    try {
      const s = await getRideSplit(rideId, n)
      setVans(s.data.vans); setSaved(false)
    } finally {
      setBusy(false)
    }
  }

  // The list a driver gets in messenger — the same shape as the book page.
  const vanText = (van, vi) => {
    const head = ride ? `Бус ${vi + 1} — ${fmtDate(ride.date)} · ${ride.route.name}` : `Бус ${vi + 1}`
    const lines = van.map((id, i) => {
      const b = bookings[id]
      if (!b) return ''
      const extra = [b.from_address && `подача: ${b.from_address}`, b.to_address && `висадка: ${b.to_address}`, b.comment]
        .filter(Boolean).join('; ')
      return `${i + 1}. ${b.from_city} – ${b.to_city} · ${b.seats} ${b.seats === 1 ? 'місце' : 'місць'} · ${b.phone}${extra ? ` (${extra})` : ''}`
    })
    return `${head}
${lines.join('\n')}
Разом: ${load(van)}`
  }

  const copy = async (text, label) => {
    // navigator.clipboard exists only on https/localhost; over a plain-http
    // tunnel fall back to the old select-and-copy trick
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const ta = document.createElement('textarea')
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0'
      document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove()
    }
    setNote(`Скопійовано: ${label}`)
  }

  const move = (bookingId, fromVan, toVan) => {
    setVans((prev) => {
      const next = prev.map((v) => v.filter((id) => id !== bookingId))
      if (toVan === 'new') next.push([bookingId])
      else next[toVan] = [...next[toVan], bookingId]
      return next.filter((v) => v.length)
    })
    setSaved(false)
  }

  const save = async () => {
    setBusy(true)
    try {
      await saveRideSplit(rideId, { vans })
      setSaved(true)
      setNote('Розподіл збережено — водії побачать свій бус у маніфесті.')
    } finally {
      setBusy(false)
    }
  }

  const today = new Date().toISOString().slice(0, 10)
  const rideOptions = rides
    .filter((r) => r.status === 'active' && (r.date >= today || String(r.id) === rideId))
    .sort((a, b) => a.date.localeCompare(b.date))

  const load = (van) => van.reduce((s, id) => s + (bookings[id]?.seats || 0), 0)
  const totalSeats = vans.reduce((s, v) => s + load(v), 0)

  return (
    <div>
      <div className="flex items-center justify-between mb-2 flex-wrap gap-3">
        <h1 className="text-2xl font-bold">Розподіл по бусах</h1>
        <select value={rideId} onChange={(e) => setRideId(e.target.value)} className="border rounded-lg px-3 py-2">
          <option value="">— оберіть рейс —</option>
          {rideOptions.map((r) => (
            <option key={r.id} value={r.id}>{fmtDate(r.date)} · {r.route.name}</option>
          ))}
        </select>
      </div>
      <p className="text-gray-500 mb-6 max-w-2xl">
        Пасажири згруповані за напрямком: сусідні міста потрапляють в один бус. До 16 людей — два буси,
        більше — три. Перекиньте того, кого поставило не туди, збережіть і скопіюйте список водієві.
      </p>

      {busy && <div className="text-gray-500">Завантаження…</div>}

      {rideId && !busy && vans.length === 0 && (
        <div className="bg-gray-100 text-gray-600 rounded-lg p-6">На цьому рейсі ще нема пасажирів.</div>
      )}

      {vans.length > 0 && (
        <>
          <div className="flex items-center gap-4 mb-4 text-sm text-gray-600">
            <span>{totalSeats} місць · {vans.length} {vans.length === 1 ? 'бус' : vans.length < 5 ? 'буси' : 'бусів'}</span>
            <span className={saved ? 'text-green-700' : 'text-amber-700'}>{saved ? '✓ збережено' : 'не збережено'}</span>
            <span className="ml-auto flex items-center gap-1">
              <span className="text-gray-400 mr-1">Розділити на:</span>
              {[1, 2, 3, 4].map((n) => (
                <button key={n} onClick={() => proposeFor(n)} disabled={busy}
                        title={n === suggested ? 'рекомендовано за кількістю людей' : ''}
                        className={`px-3 py-1 rounded-lg border ${n === suggested ? 'border-blue-700 text-blue-700 font-semibold' : 'border-gray-300 text-gray-600 hover:bg-gray-50'}`}>
                  {n}
                </button>
              ))}
            </span>
            <button onClick={() => copy(vans.map(vanText).join('\n\n'), 'усі буси')}
                    className="border border-gray-300 rounded-lg px-3 py-2 hover:bg-gray-50">
              Скопіювати все
            </button>
            <button onClick={save} disabled={busy}
                    className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg px-5 py-2">
              Зберегти
            </button>
          </div>
          {note && <div className="bg-green-50 text-green-800 rounded-lg px-3 py-2 mb-4 text-sm">{note}</div>}

          <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${Math.min(vans.length, 4)}, minmax(0, 1fr))` }}>
            {vans.map((van, vi) => {
              const seats = load(van)
              const over = seats > capacity
              return (
                <div key={vi} className={`bg-white rounded-lg shadow-sm p-3 ${over ? 'ring-2 ring-red-400' : ''}`}>
                  <div className="flex items-baseline justify-between mb-2 gap-2">
                    <div className="font-semibold">Бус {vi + 1}</div>
                    <div className="flex items-baseline gap-3">
                      <button onClick={() => copy(vanText(van, vi), `бус ${vi + 1}`)} className="text-xs text-blue-700 hover:underline">
                        копіювати
                      </button>
                      <div className={`text-sm ${over ? 'text-red-600 font-semibold' : 'text-gray-500'}`}>{seats} / {capacity}</div>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {van.map((id) => {
                      const b = bookings[id]
                      if (!b) return null
                      return (
                        <div key={id} className="border rounded-lg p-2 text-sm">
                          <div className="font-medium">{b.from_city} → {b.to_city}</div>
                          <div className="text-gray-500 flex justify-between">
                            <span>{b.seats} {b.seats === 1 ? 'місце' : 'місць'} · {b.phone}</span>
                          </div>
                          <select value={vi} onChange={(e) => move(id, vi, e.target.value === 'new' ? 'new' : Number(e.target.value))}
                                  className="mt-1 text-xs border rounded px-1 py-0.5 w-full text-gray-600">
                            {vans.map((_, j) => <option key={j} value={j}>→ бус {j + 1}</option>)}
                            <option value="new">→ новий бус</option>
                          </select>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
