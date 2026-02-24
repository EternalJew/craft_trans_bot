/**
 * StopEditor — editable ordered list of route stops.
 * Props:
 *   stops: array of { city, country, order, pickup, dropoff }
 *   onChange: (newStops) => void
 */
export default function StopEditor({ stops, onChange }) {
  const update = (index, field, value) => {
    const next = stops.map((s, i) => (i === index ? { ...s, [field]: value } : s))
    onChange(next)
  }

  const addStop = () => {
    onChange([...stops, { city: '', country: 'UA', order: stops.length, pickup: true, dropoff: true }])
  }

  const removeStop = (index) => {
    onChange(stops.filter((_, i) => i !== index).map((s, i) => ({ ...s, order: i })))
  }

  const move = (index, dir) => {
    const next = [...stops]
    const target = index + dir
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next.map((s, i) => ({ ...s, order: i })))
  }

  return (
    <div className="space-y-2">
      {stops.map((stop, i) => (
        <div key={i} className="flex items-center gap-2 bg-gray-50 border rounded p-2">
          <span className="text-gray-400 text-xs w-5">{i + 1}</span>

          <input
            className="border rounded px-2 py-1 text-sm flex-1"
            placeholder="Місто"
            value={stop.city}
            onChange={(e) => update(i, 'city', e.target.value)}
          />

          <select
            className="border rounded px-2 py-1 text-sm w-20"
            value={stop.country}
            onChange={(e) => update(i, 'country', e.target.value)}
          >
            {['UA', 'CZ', 'PL', 'SK', 'AT', 'DE'].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>

          <label className="flex items-center gap-1 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={stop.pickup}
              onChange={(e) => update(i, 'pickup', e.target.checked)}
            />
            Посадка
          </label>

          <label className="flex items-center gap-1 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={stop.dropoff}
              onChange={(e) => update(i, 'dropoff', e.target.checked)}
            />
            Висадка
          </label>

          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => move(i, -1)}
              disabled={i === 0}
              className="text-gray-400 hover:text-gray-700 disabled:opacity-30 text-sm px-1"
            >
              ↑
            </button>
            <button
              type="button"
              onClick={() => move(i, 1)}
              disabled={i === stops.length - 1}
              className="text-gray-400 hover:text-gray-700 disabled:opacity-30 text-sm px-1"
            >
              ↓
            </button>
            <button
              type="button"
              onClick={() => removeStop(i)}
              className="text-red-400 hover:text-red-600 text-sm px-1"
            >
              ✕
            </button>
          </div>
        </div>
      ))}

      <button
        type="button"
        onClick={addStop}
        className="w-full border-2 border-dashed border-gray-300 rounded py-2 text-sm text-gray-500 hover:border-blue-400 hover:text-blue-600 transition"
      >
        + Додати зупинку
      </button>
    </div>
  )
}
