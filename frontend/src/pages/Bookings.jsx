import { useEffect, useState } from 'react'
import { getRides, getRideBookings, cancelBooking } from '../api'

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

  const statusColor = (s) =>
    s === 'confirmed' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'

  const selectedRideData = rides.find((r) => String(r.id) === String(selectedRide))

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Бронювання</h1>
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
          <div className="mt-3 flex gap-6 text-sm text-gray-600">
            <span>Транспорт: <b>{selectedRideData.vehicle || '—'}</b></span>
            <span>Водій: <b>{selectedRideData.driver || '—'}</b></span>
            <span>Ціна: <b>{selectedRideData.price ? `${selectedRideData.price} грн` : '—'}</b></span>
            <span>
              Заповненість:{' '}
              <b>
                {selectedRideData.seats_total - selectedRideData.seats_free}/
                {selectedRideData.seats_total}
              </b>
            </span>
          </div>
        )}
      </div>

      {/* Bookings table */}
      {selectedRide && (
        <div className="bg-white rounded-xl shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
              <tr>
                <th className="px-4 py-3 text-left">ID</th>
                <th className="px-4 py-3 text-left">ПІБ</th>
                <th className="px-4 py-3 text-left">Телефон</th>
                <th className="px-4 py-3 text-left">Звідки → Куди</th>
                <th className="px-4 py-3 text-left">Місць</th>
                <th className="px-4 py-3 text-left">Коментар</th>
                <th className="px-4 py-3 text-left">Дата бронювання</th>
                <th className="px-4 py-3 text-left">Статус</th>
                <th className="px-4 py-3"></th>
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
                  <td className="px-4 py-3 text-gray-400">#{b.id}</td>
                  <td className="px-4 py-3 font-medium">{b.name}</td>
                  <td className="px-4 py-3 text-gray-600">{b.phone}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {b.from_stop?.city || '—'} → {b.to_stop?.city || '—'}
                  </td>
                  <td className="px-4 py-3 text-center">{b.seats}</td>
                  <td className="px-4 py-3 text-gray-500 max-w-xs truncate">{b.comment || '—'}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {new Date(b.created_at).toLocaleDateString('uk-UA')}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor(b.status)}`}>
                      {b.status === 'confirmed' ? 'Підтверджено' : 'Скасовано'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
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
