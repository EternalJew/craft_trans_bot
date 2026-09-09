import { useEffect, useState } from 'react'
import { getRides, getRideBookings, cancelBooking, updateBooking } from '../api'

const PICKUP_LABELS = {
  waiting:     { label: 'Очікує',     color: 'bg-gray-100 text-gray-600' },
  picked_up:   { label: 'Забрано',    color: 'bg-blue-100 text-blue-700' },
  no_show:     { label: 'Не вийшов',  color: 'bg-orange-100 text-orange-700' },
  dropped_off: { label: 'Висаджено',  color: 'bg-green-100 text-green-700' },
}

export default function BookingsPage() {
  const [rides, setRides]         = useState([])
  const [selectedRide, setSelected] = useState('')
  const [bookings, setBookings]   = useState([])
  const [loading, setLoading]     = useState(false)

  useEffect(() => {
    getRides().then((res) => setRides(res.data))
  }, [])

  const loadBookings = async (rideId) => {
    if (!rideId) { setBookings([]); return }
    setLoading(true)
    try {
      const res = await getRideBookings(rideId)
      setBookings(res.data)
    } finally {
      setLoading(false)
    }
  }

  const handleRideChange = (e) => {
    setSelected(e.target.value)
    loadBookings(e.target.value)
  }

  const handleCancel = async (id) => {
    if (!confirm('Скасувати бронювання?')) return
    await cancelBooking(id)
    loadBookings(selectedRide)
  }

  const handlePickupTime = async (booking) => {
    const value = prompt(
      `Час подачі для ${booking.name} (напр. 07:20). Потрапить у нагадування.`,
      booking.pickup_time?.slice(0, 5) || '',
    )
    if (value === null) return
    await updateBooking(booking.id, { pickup_time: value.trim() || null })
    loadBookings(selectedRide)
  }

  const selectedRideData = rides.find((r) => String(r.id) === String(selectedRide))
  const totalCash = bookings.reduce((sum, b) => sum + (b.cash_collected || 0), 0)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Бронювання</h1>
        {selectedRide && bookings.length > 0 && (
          <button
            onClick={() => window.print()}
            className="border px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 print:hidden"
          >
            🖨 Друк списку
          </button>
        )}
      </div>

      {/* Ride selector */}
      <div className="bg-white rounded-xl shadow p-4 mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">Оберіть рейс</label>
        <select
          className="border rounded-lg px-3 py-2 text-sm w-full max-w-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          value={selectedRide}
          onChange={handleRideChange}
        >
          <option value="">— Оберіть рейс —</option>
          {rides.map((r) => (
            <option key={r.id} value={r.id}>
              {r.date} | {r.route?.name} | {r.seats_free}/{r.seats_total} вільно
            </option>
          ))}
        </select>

        {selectedRideData && (
          <div className="mt-3 flex gap-6 text-sm text-gray-600 flex-wrap">
            <span>Транспорт: <b>{selectedRideData.vehicle || '—'}</b></span>
            <span>Водій: <b>{selectedRideData.driver?.full_name || '—'}</b></span>
            <span>Виїзд: <b>{selectedRideData.departure_time?.slice(0, 5) || '—'}</b></span>
            <span>Ціна: <b>{selectedRideData.price ? `${selectedRideData.price} грн` : '—'}</b></span>
            <span>
              Заповненість:{' '}
              <b>
                {selectedRideData.seats_total - selectedRideData.seats_free}/
                {selectedRideData.seats_total}
              </b>
            </span>
            <span>Готівка зібрана: <b>{totalCash} грн</b></span>
          </div>
        )}
      </div>

      {/* Bookings table */}
      {selectedRide && (
        <div className="bg-white rounded-xl shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 text-left">ПІБ</th>
                <th className="px-4 py-3 text-left">Телефон</th>
                <th className="px-4 py-3 text-left">Звідки → Куди</th>
                <th className="px-4 py-3 text-left">Подача</th>
                <th className="px-4 py-3 text-left">Місць</th>
                <th className="px-4 py-3 text-left">Коментар</th>
                <th className="px-4 py-3 text-left">На маршруті</th>
                <th className="px-4 py-3 text-left">Готівка</th>
                <th className="px-4 py-3 print:hidden"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading && (
                <tr>
                  <td colSpan={9} className="text-center py-8 text-gray-400">Завантаження...</td>
                </tr>
              )}
              {!loading && bookings.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center py-8 text-gray-400">
                    Броней на цей рейс немає
                  </td>
                </tr>
              )}
              {bookings.map((b) => (
                <tr key={b.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium">{b.name}</div>
                    {b.source === 'web' && (
                      <div className="text-xs text-gray-400">із сайту</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{b.phone}</td>
                  <td className="px-4 py-3 text-gray-600">
                    <div>{b.from_stop?.city || '—'} → {b.to_stop?.city || '—'}</div>
                    {(b.from_address || b.to_address) && (
                      <div className="text-xs text-gray-400">
                        {b.from_address || '—'} → {b.to_address || '—'}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handlePickupTime(b)}
                      className="text-sm text-blue-600 hover:text-blue-800 print:text-gray-900"
                    >
                      {b.pickup_time ? b.pickup_time.slice(0, 5) : 'вказати'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-center">{b.seats}</td>
                  <td className="px-4 py-3 text-gray-500 max-w-xs truncate">{b.comment || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${PICKUP_LABELS[b.pickup_status]?.color}`}>
                      {PICKUP_LABELS[b.pickup_status]?.label || b.pickup_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {b.cash_collected != null ? `${b.cash_collected} грн` : '—'}
                  </td>
                  <td className="px-4 py-3 print:hidden">
                    {b.status === 'confirmed' && (
                      <button
                        onClick={() => handleCancel(b.id)}
                        className="text-red-400 hover:text-red-600 text-sm"
                      >
                        Скасувати
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
