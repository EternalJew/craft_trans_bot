import { useEffect, useState } from 'react'
import { getBookQueue, getRides, markWrittenInBook } from '../api'

const SOURCE_LABELS = {
  web:    { label: 'Сайт',    color: 'bg-blue-100 text-blue-700' },
  bot:    { label: 'Бот',     color: 'bg-violet-100 text-violet-700' },
  admin:  { label: 'Дзвінок', color: 'bg-amber-100 text-amber-700' },
  driver: { label: 'Водій',   color: 'bg-green-100 text-green-700' },
}

const fmtDate = (iso) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('uk-UA', { weekday: 'short', day: 'numeric', month: 'long' })

const fmtTaken = (iso) => new Date(iso).toLocaleString('uk-UA', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

export default function BookQueuePage() {
  const [bookings, setBookings] = useState([])
  const [rides, setRides]       = useState({})
  const [loading, setLoading]   = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [queue, rideList] = await Promise.all([getBookQueue(), getRides()])
      setBookings(queue.data)
      setRides(Object.fromEntries(rideList.data.map((r) => [r.id, r])))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const markWritten = async (id) => {
    await markWrittenInBook(id)
    setBookings((prev) => prev.filter((b) => b.id !== id))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-bold">На запис у книжку</h1>
        <button onClick={load} className="text-sm text-blue-700 hover:underline">Оновити</button>
      </div>
      <p className="text-gray-500 mb-6 max-w-2xl">
        Бронювання, які прийшли з сайту, бота чи по телефону і ще не перенесені в книжку.
        Той самий список приходить власнику в Telegram — тут видно, що він уже підтвердив.
      </p>

      {loading && <div className="text-gray-500">Завантаження…</div>}

      {!loading && bookings.length === 0 && (
        <div className="bg-green-50 text-green-800 rounded-lg p-6">
          Порожньо — усе перенесено в книжку.
        </div>
      )}

      <div className="space-y-3">
        {bookings.map((b) => {
          const ride = rides[b.ride_id]
          const source = SOURCE_LABELS[b.source] || { label: b.source, color: 'bg-gray-100 text-gray-600' }
          return (
            <div key={b.id} className="bg-white rounded-lg shadow-sm p-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${source.color}`}>{source.label}</span>
                  <span className="text-xs text-gray-400">
                    №{b.id} · прийнято {fmtTaken(b.created_at)}
                  </span>
                </div>
                <div className="font-semibold mt-1">
                  {ride ? `${fmtDate(ride.date)} · ${ride.route.name}` : `Рейс #${b.ride_id}`}
                </div>
                <div className="text-gray-800">
                  {b.name} — <a href={`tel:${b.phone}`} className="text-blue-700">{b.phone}</a>
                </div>
                <div className="text-gray-600">
                  {b.from_city} → {b.to_city} · {b.seats} місць
                </div>
                {(b.from_address || b.to_address) && (
                  <div className="text-sm text-gray-500 mt-1">
                    {b.from_address && <>Подача: {b.from_address}. </>}
                    {b.to_address && <>Висадка: {b.to_address}.</>}
                  </div>
                )}
                {b.comment && <div className="text-sm text-gray-500 italic mt-1">{b.comment}</div>}
              </div>
              <button
                onClick={() => markWritten(b.id)}
                className="shrink-0 bg-green-600 hover:bg-green-700 text-white text-sm px-4 py-2 rounded-lg"
              >
                Записано
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
