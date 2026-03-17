import { useState, useRef, useEffect } from 'react'
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// ── Icons ─────────────────────────────────────────────────────────────────────

const makeIcon = (color, label) =>
  L.divIcon({
    html: `<div style="
      background:${color};color:#fff;border-radius:50%;
      width:30px;height:30px;display:flex;align-items:center;
      justify-content:center;font-weight:bold;font-size:13px;
      border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.45);
      line-height:1
    ">${label}</div>`,
    className: '',
    iconSize:   [30, 30],
    iconAnchor: [15, 15],
    popupAnchor:[0, -18],
  })

// ── API helpers ───────────────────────────────────────────────────────────────

async function geocode(address) {
  await new Promise(r => setTimeout(r, 350)) // Nominatim rate limit
  const url =
    `https://nominatim.openstreetmap.org/search` +
    `?q=${encodeURIComponent(address)}&format=json&limit=1`
  const res = await fetch(url, {
    headers: { 'Accept-Language': 'uk,en', 'User-Agent': 'CraftTransBot/1.0' },
  })
  const data = await res.json()
  if (!data.length) throw new Error(`Адресу не знайдено: "${address}"`)
  return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) }
}

// Nearest-neighbor TSP starting from the easternmost point (closest to Ukraine border)
function optimizeOrder(points) {
  if (points.length <= 1) return points.map((_, i) => i)

  // Start from easternmost point (highest longitude) — first city when entering from Ukraine
  let start = 0
  for (let i = 1; i < points.length; i++) {
    if (points[i].lng > points[start].lng) start = i
  }

  const visited = new Set([start])
  const order   = [start]

  while (order.length < points.length) {
    const cur = points[order[order.length - 1]]
    let nearest = -1, nearestDist = Infinity
    for (let i = 0; i < points.length; i++) {
      if (visited.has(i)) continue
      const d = (cur.lng - points[i].lng) ** 2 + (cur.lat - points[i].lat) ** 2
      if (d < nearestDist) { nearestDist = d; nearest = i }
    }
    visited.add(nearest)
    order.push(nearest)
  }
  return order
}

// Returns { geometry: [[lat,lng],...], order: [inputIndex,...] }
async function fetchOptimizedRoute(points) {
  if (points.length < 2) return { geometry: [], order: [0] }

  const order        = optimizeOrder(points)
  const sortedPoints = order.map(i => points[i])

  const coords = sortedPoints.map(p => `${p.lng},${p.lat}`).join(';')
  const url    =
    `https://router.project-osrm.org/route/v1/driving/${coords}` +
    `?overview=full&geometries=geojson`
  const res  = await fetch(url)
  const data = await res.json()
  if (data.code !== 'Ok') throw new Error('Не вдалося побудувати маршрут (OSRM)')

  const geometry = data.routes[0].geometry.coordinates.map(([lng, lat]) => [lat, lng])
  return { geometry, order }
}

// ── AutoBounds: fits map to all visible markers ────────────────────────────────

function AutoBounds({ allMarkers, trigger }) {
  const map = useMap()
  useEffect(() => {
    if (!allMarkers.length) return
    map.fitBounds(allMarkers.map(m => [m.lat, m.lng]), { padding: [40, 40] })
  }, [trigger]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

// ── Main component ────────────────────────────────────────────────────────────

const mkPassenger = (id) => ({ id, name: '', address: '' })
const mkParcel    = (id) => ({ id, description: '', address: '' })

export default function DriverMap() {
  const nextId = useRef(2)

  const [passengers, setPassengers] = useState([mkPassenger(1)])
  const [parcels,    setParcels]    = useState([mkParcel(1)])
  const [mode,       setMode]       = useState('both')

  const [loading,          setLoading]          = useState(false)
  const [error,            setError]            = useState('')
  const [passengerMarkers, setPassengerMarkers] = useState([])
  const [parcelMarkers,    setParcelMarkers]    = useState([])
  const [passengerRoute,   setPassengerRoute]   = useState([])
  const [parcelRoute,      setParcelRoute]      = useState([])
  const [boundsTrigger,    setBoundsTrigger]    = useState(0)

  // ── Passenger helpers ──────────────────────────────────────────────────────
  const addPassenger = () => {
    if (passengers.length >= 8) return
    setPassengers(p => [...p, mkPassenger(nextId.current++)])
  }
  const removePassenger = id => setPassengers(p => p.filter(x => x.id !== id))
  const updatePassenger = (id, field, val) =>
    setPassengers(p => p.map(x => x.id === id ? { ...x, [field]: val } : x))

  // ── Parcel helpers ─────────────────────────────────────────────────────────
  const addParcel    = () => setParcels(p => [...p, mkParcel(nextId.current++)])
  const removeParcel = id  => setParcels(p => p.filter(x => x.id !== id))
  const updateParcel = (id, field, val) =>
    setParcels(p => p.map(x => x.id === id ? { ...x, [field]: val } : x))

  // ── Build route ────────────────────────────────────────────────────────────
  const buildRoute = async () => {
    setError('')
    setLoading(true)
    setPassengerMarkers([])
    setParcelMarkers([])
    setPassengerRoute([])
    setParcelRoute([])

    try {
      const activeP = passengers.filter(p => p.name.trim() && p.address.trim())
      const activeC = parcels.filter(p => p.description.trim() && p.address.trim())

      if (!activeP.length && !activeC.length) {
        setError('Заповніть хоча б одного пасажира або одну посилку')
        return
      }

      // Geocode passengers
      const pGeo = []
      for (const p of activeP) {
        const geo = await geocode(p.address)
        pGeo.push({ ...p, ...geo })
      }

      // Geocode parcels
      const cGeo = []
      for (const c of activeC) {
        const geo = await geocode(c.address)
        cGeo.push({ ...c, ...geo })
      }

      if (pGeo.length >= 2) {
        const { geometry, order } = await fetchOptimizedRoute(pGeo)
        setPassengerRoute(geometry)
        setPassengerMarkers(order.map(i => pGeo[i]))
      } else {
        setPassengerMarkers(pGeo)
      }

      if (cGeo.length >= 2) {
        const { geometry, order } = await fetchOptimizedRoute(cGeo)
        setParcelRoute(geometry)
        setParcelMarkers(order.map(i => cGeo[i]))
      } else {
        setParcelMarkers(cGeo)
      }

      setBoundsTrigger(n => n + 1)
    } catch (e) {
      setError(e.message || 'Помилка')
    } finally {
      setLoading(false)
    }
  }

  const showP = mode === 'both' || mode === 'passengers'
  const showC = mode === 'both' || mode === 'parcels'

  const allVisibleMarkers = [
    ...(showP ? passengerMarkers : []),
    ...(showC ? parcelMarkers    : []),
  ]

  return (
    <div className="flex gap-4" style={{ height: 'calc(100vh - 48px)' }}>

      {/* ── Left panel ── */}
      <div className="w-80 flex-shrink-0 flex flex-col gap-3 overflow-y-auto pr-1">

        {/* Passengers */}
        <div className="bg-white rounded-xl shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-bold text-sm flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-blue-600 inline-block" />
              Пасажири ({passengers.length}/8)
            </h2>
            <button
              onClick={addPassenger}
              disabled={passengers.length >= 8}
              className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded hover:bg-blue-200 disabled:opacity-40"
            >
              + Додати
            </button>
          </div>

          <div className="space-y-3">
            {passengers.map((p, i) => (
              <div key={p.id} className="border border-blue-200 rounded-lg p-3 space-y-2 bg-blue-50">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-blue-700">
                    Пасажир {i + 1}
                  </span>
                  {passengers.length > 1 && (
                    <button
                      onClick={() => removePassenger(p.id)}
                      className="text-red-400 hover:text-red-600 text-xs leading-none"
                    >✕</button>
                  )}
                </div>
                <input
                  className="w-full border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                  placeholder="ПІБ пасажира"
                  value={p.name}
                  onChange={e => updatePassenger(p.id, 'name', e.target.value)}
                />
                <input
                  className="w-full border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                  placeholder="Адреса в Чехії (Прага, 5 kvetna 425)"
                  value={p.address}
                  onChange={e => updatePassenger(p.id, 'address', e.target.value)}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Parcels */}
        <div className="bg-white rounded-xl shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-bold text-sm flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500 inline-block" />
              Посилки ({parcels.length})
            </h2>
            <button
              onClick={addParcel}
              className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded hover:bg-red-200"
            >
              + Додати
            </button>
          </div>

          <div className="space-y-3">
            {parcels.map((p, i) => (
              <div key={p.id} className="border border-red-200 rounded-lg p-3 space-y-2 bg-red-50">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-red-700">
                    Посилка {i + 1}
                  </span>
                  {parcels.length > 1 && (
                    <button
                      onClick={() => removeParcel(p.id)}
                      className="text-red-400 hover:text-red-600 text-xs leading-none"
                    >✕</button>
                  )}
                </div>
                <input
                  className="w-full border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-red-400"
                  placeholder="Опис (пакет АТБ, одяг...)"
                  value={p.description}
                  onChange={e => updateParcel(p.id, 'description', e.target.value)}
                />
                <input
                  className="w-full border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-red-400"
                  placeholder="Адреса (Мост, Fibicka 14)"
                  value={p.address}
                  onChange={e => updateParcel(p.id, 'address', e.target.value)}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Build button */}
        <button
          onClick={buildRoute}
          disabled={loading}
          className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-xl disabled:opacity-50 transition text-sm"
        >
          {loading ? 'Будуємо маршрут…' : '🗺 Побудувати маршрут'}
        </button>

        {error && (
          <p className="text-red-600 text-xs text-center bg-red-50 rounded-lg p-2">{error}</p>
        )}

        {/* Mode toggle */}
        <div className="bg-white rounded-xl shadow p-3">
          <p className="text-xs text-gray-400 mb-2 font-medium uppercase tracking-wide">
            Показати на карті
          </p>
          <div className="flex gap-2">
            {[
              { v: 'both',       label: 'Всіх',       color: 'bg-gray-800' },
              { v: 'passengers', label: 'Пасажирів',  color: 'bg-blue-600' },
              { v: 'parcels',    label: 'Посилки',    color: 'bg-red-500'  },
            ].map(({ v, label, color }) => (
              <button
                key={v}
                onClick={() => setMode(v)}
                className={`flex-1 text-xs py-1.5 rounded font-medium transition ${
                  mode === v
                    ? `${color} text-white`
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Legend */}
        {(passengerMarkers.length > 0 || parcelMarkers.length > 0) && (
          <div className="bg-white rounded-xl shadow p-3 text-xs space-y-1">
            <p className="font-semibold text-gray-600 mb-1">Зупинки:</p>
            {passengerMarkers.map((p, i) => (
              <div key={p.id} className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0">{i+1}</span>
                <span className="text-gray-700 truncate">{p.name}</span>
              </div>
            ))}
            {parcelMarkers.map((p, i) => (
              <div key={p.id} className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center font-bold text-xs flex-shrink-0">{i+1}</span>
                <span className="text-gray-700 truncate">{p.description}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Map ── */}
      <div className="flex-1 rounded-xl overflow-hidden shadow relative">
        {loading && (
          <div className="absolute inset-0 bg-white/60 z-[1000] flex items-center justify-center">
            <div className="bg-white rounded-xl shadow-lg px-6 py-4 text-sm font-medium text-gray-700">
              Геокодуємо адреси та будуємо маршрут…
            </div>
          </div>
        )}
        <MapContainer
          center={[50.08, 14.44]}
          zoom={7}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='© <a href="https://openstreetmap.org">OpenStreetMap</a>'
          />

          <AutoBounds allMarkers={allVisibleMarkers} trigger={boundsTrigger} />

          {/* Passenger route */}
          {showP && passengerRoute.length >= 2 && (
            <Polyline positions={passengerRoute} color="#2563eb" weight={5} opacity={0.85} />
          )}

          {/* Parcel route */}
          {showC && parcelRoute.length >= 2 && (
            <Polyline positions={parcelRoute} color="#dc2626" weight={5} opacity={0.85} />
          )}

          {/* Passenger markers */}
          {showP && passengerMarkers.map((p, i) => (
            <Marker key={p.id} position={[p.lat, p.lng]} icon={makeIcon('#2563eb', i + 1)}>
              <Popup>
                <b className="text-blue-700">{p.name}</b>
                <br />
                <span className="text-gray-500 text-xs">{p.address}</span>
              </Popup>
            </Marker>
          ))}

          {/* Parcel markers */}
          {showC && parcelMarkers.map((p, i) => (
            <Marker key={p.id} position={[p.lat, p.lng]} icon={makeIcon('#dc2626', i + 1)}>
              <Popup>
                <b className="text-red-600">Посилка {i + 1}</b>
                <br />
                <span className="text-gray-700 text-xs">{p.description}</span>
                <br />
                <span className="text-gray-500 text-xs">{p.address}</span>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  )
}
