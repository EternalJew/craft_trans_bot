import { useState, useEffect } from 'react'
import api from '../api'

const WORK_TYPES = {
  oil_change:  'Заміна масла',
  brake_pads:  'Гальмівні колодки',
  timing_belt: 'ГРМ',
  tires:       'Шини',
  filters:     'Фільтри',
  battery:     'АКБ',
  other:       'Інше',
}

const today = () => new Date().toISOString().slice(0, 10)

function ServiceAlert({ record, currentMileage }) {
  if (!record.next_service_km) return null
  const remaining = record.next_service_km - currentMileage
  if (remaining > 1000) return null
  return (
    <span className={`ml-2 text-xs font-semibold px-2 py-0.5 rounded-full ${
      remaining <= 0 ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
    }`}>
      {remaining <= 0
        ? `Прострочено на ${Math.abs(remaining).toLocaleString()} км`
        : `Через ${remaining.toLocaleString()} км`}
    </span>
  )
}

function VehicleCard({ v, onUpdated, onDeleted }) {
  const [expanded, setExpanded]   = useState(false)
  const [showForm, setShowForm]   = useState(false)
  const [mileageEdit, setMEditing] = useState(false)
  const [newMileage, setNewMileage] = useState(v.mileage_current)
  const [rec, setRec] = useState({
    date: today(), mileage: v.mileage_current, work_type: 'oil_change',
    description: '', cost: '', next_service_km: '',
  })

  const saveMileage = async () => {
    await api.patch(`/api/vehicles/${v.id}`, { mileage_current: Number(newMileage) })
    setMEditing(false)
    onUpdated()
  }

  const addRecord = async e => {
    e.preventDefault()
    await api.post(`/api/vehicles/${v.id}/maintenance`, {
      ...rec,
      mileage:         Number(rec.mileage),
      cost:            rec.cost       ? Number(rec.cost)            : null,
      next_service_km: rec.next_service_km ? Number(rec.next_service_km) : null,
    })
    setShowForm(false)
    setRec({ date: today(), mileage: v.mileage_current, work_type: 'oil_change', description: '', cost: '', next_service_km: '' })
    onUpdated()
  }

  const deleteRecord = async id => {
    if (!confirm('Видалити запис?')) return
    await api.delete(`/api/vehicles/maintenance/${id}`)
    onUpdated()
  }

  // Upcoming alerts: latest record per work_type with next_service_km
  const alerts = []
  const seen = new Set()
  for (const r of v.maintenance) {
    if (r.next_service_km && !seen.has(r.work_type)) {
      seen.add(r.work_type)
      const remaining = r.next_service_km - v.mileage_current
      if (remaining <= 1000) alerts.push({ ...r, remaining })
    }
  }

  return (
    <div className="bg-white rounded-xl shadow mb-4">
      <div
        className="flex items-center justify-between p-4 cursor-pointer"
        onClick={() => setExpanded(x => !x)}
      >
        <div>
          <span className="font-semibold text-gray-800 text-lg">{v.name}</span>
          <span className="ml-3 text-sm text-gray-500">{v.plate}</span>
          {v.make && <span className="ml-2 text-sm text-gray-400">{v.make} {v.model_name} {v.year || ''}</span>}
        </div>
        <div className="flex items-center gap-3">
          {alerts.length > 0 && (
            <span className="text-xs bg-red-100 text-red-700 font-semibold px-2 py-1 rounded-full">
              {alerts.length} нагадування
            </span>
          )}
          <div className="text-right">
            {mileageEdit ? (
              <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                <input
                  type="number"
                  value={newMileage}
                  onChange={e => setNewMileage(e.target.value)}
                  className="w-28 border rounded px-2 py-1 text-sm"
                />
                <button onClick={saveMileage} className="text-xs bg-blue-600 text-white px-2 py-1 rounded">Зберегти</button>
                <button onClick={() => setMEditing(false)} className="text-xs text-gray-500">Скасувати</button>
              </div>
            ) : (
              <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                <span className="text-sm font-medium text-gray-700">{v.mileage_current.toLocaleString()} км</span>
                <button onClick={() => { setMEditing(true); setNewMileage(v.mileage_current) }} className="text-xs text-blue-600 hover:underline">змінити</button>
              </div>
            )}
          </div>
          <span className="text-gray-400 text-lg">{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {expanded && (
        <div className="border-t px-4 pb-4">
          {/* Alerts */}
          {alerts.map(a => (
            <div key={a.id} className={`mt-3 text-sm px-3 py-2 rounded-lg ${
              a.remaining <= 0 ? 'bg-red-50 text-red-700' : 'bg-yellow-50 text-yellow-700'
            }`}>
              {a.remaining <= 0 ? '🔴' : '🟡'} <strong>{WORK_TYPES[a.work_type] || a.work_type}</strong>
              {a.remaining <= 0
                ? ` — прострочено на ${Math.abs(a.remaining).toLocaleString()} км (потрібно було при ${a.next_service_km.toLocaleString()} км)`
                : ` — через ${a.remaining.toLocaleString()} км (при ${a.next_service_km.toLocaleString()} км)`}
            </div>
          ))}

          {/* History */}
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium text-gray-700 text-sm">Журнал обслуговування</span>
              <button
                onClick={() => setShowForm(x => !x)}
                className="text-xs bg-blue-600 text-white px-3 py-1 rounded-lg hover:bg-blue-700"
              >
                + Додати запис
              </button>
            </div>

            {showForm && (
              <form onSubmit={addRecord} className="bg-gray-50 rounded-lg p-3 mb-3 grid grid-cols-2 gap-2 text-sm">
                <div>
                  <label className="text-xs text-gray-600">Дата</label>
                  <input type="date" value={rec.date} onChange={e => setRec(r => ({ ...r, date: e.target.value }))}
                    className="w-full border rounded px-2 py-1" required />
                </div>
                <div>
                  <label className="text-xs text-gray-600">Пробіг (км)</label>
                  <input type="number" value={rec.mileage} onChange={e => setRec(r => ({ ...r, mileage: e.target.value }))}
                    className="w-full border rounded px-2 py-1" required />
                </div>
                <div>
                  <label className="text-xs text-gray-600">Вид роботи</label>
                  <select value={rec.work_type} onChange={e => setRec(r => ({ ...r, work_type: e.target.value }))}
                    className="w-full border rounded px-2 py-1">
                    {Object.entries(WORK_TYPES).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-600">Вартість (€)</label>
                  <input type="number" step="0.01" value={rec.cost} onChange={e => setRec(r => ({ ...r, cost: e.target.value }))}
                    className="w-full border rounded px-2 py-1" placeholder="необов'язково" />
                </div>
                <div className="col-span-2">
                  <label className="text-xs text-gray-600">Опис</label>
                  <input type="text" value={rec.description} onChange={e => setRec(r => ({ ...r, description: e.target.value }))}
                    className="w-full border rounded px-2 py-1" placeholder="деталі" />
                </div>
                <div className="col-span-2">
                  <label className="text-xs text-gray-600">Наступне ТО при (км)</label>
                  <input type="number" value={rec.next_service_km} onChange={e => setRec(r => ({ ...r, next_service_km: e.target.value }))}
                    className="w-full border rounded px-2 py-1" placeholder="напр. 155000" />
                </div>
                <div className="col-span-2 flex gap-2">
                  <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-blue-700">Зберегти</button>
                  <button type="button" onClick={() => setShowForm(false)} className="text-sm text-gray-500 hover:text-gray-700">Скасувати</button>
                </div>
              </form>
            )}

            {v.maintenance.length === 0 ? (
              <p className="text-sm text-gray-400 italic">Записів немає</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-500 border-b">
                    <th className="text-left py-1">Дата</th>
                    <th className="text-left py-1">Пробіг</th>
                    <th className="text-left py-1">Вид роботи</th>
                    <th className="text-left py-1">Опис</th>
                    <th className="text-left py-1">Вартість</th>
                    <th className="text-left py-1">Наст. ТО</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {v.maintenance.map(r => (
                    <tr key={r.id} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="py-1.5">{r.date}</td>
                      <td className="py-1.5">{r.mileage.toLocaleString()} км</td>
                      <td className="py-1.5">
                        {WORK_TYPES[r.work_type] || r.work_type}
                        <ServiceAlert record={r} currentMileage={v.mileage_current} />
                      </td>
                      <td className="py-1.5 text-gray-500">{r.description || '—'}</td>
                      <td className="py-1.5">{r.cost != null ? `${r.cost} €` : '—'}</td>
                      <td className="py-1.5">{r.next_service_km ? `${r.next_service_km.toLocaleString()} км` : '—'}</td>
                      <td className="py-1.5">
                        <button onClick={() => deleteRecord(r.id)} className="text-red-400 hover:text-red-600 text-xs">✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <button
            onClick={() => { if (confirm(`Видалити ${v.name}?`)) onDeleted(v.id) }}
            className="mt-4 text-xs text-red-400 hover:text-red-600"
          >
            Видалити автомобіль
          </button>
        </div>
      )}
    </div>
  )
}

const emptyForm = { name: '', plate: '', make: '', model_name: '', year: '', mileage_current: 0, notes: '' }

export default function Vehicles() {
  const [vehicles, setVehicles] = useState([])
  const [showAdd, setShowAdd]   = useState(false)
  const [form, setForm]         = useState(emptyForm)

  const load = () => api.get('/api/vehicles').then(r => setVehicles(r.data))
  useEffect(() => { load() }, [])

  const submit = async e => {
    e.preventDefault()
    await api.post('/api/vehicles', {
      ...form,
      year:            form.year            ? Number(form.year)            : null,
      mileage_current: Number(form.mileage_current),
    })
    setShowAdd(false)
    setForm(emptyForm)
    load()
  }

  const deleteVehicle = async id => {
    await api.delete(`/api/vehicles/${id}`)
    load()
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Автопарк</h1>
        <button onClick={() => setShowAdd(x => !x)} className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          + Додати авто
        </button>
      </div>

      {showAdd && (
        <form onSubmit={submit} className="bg-white rounded-xl shadow p-5 mb-6 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <div className="col-span-2 md:col-span-3 font-semibold text-gray-700">Новий автомобіль</div>
          {[
            ['name',            'Назва *',         'Ford Transit #1'],
            ['plate',           'Номер *',         'АА1234ВВ'],
            ['make',            'Марка',           'Ford'],
            ['model_name',      'Модель',          'Transit'],
            ['year',            'Рік',             '2019'],
            ['mileage_current', 'Поточний пробіг (км) *', '120000'],
          ].map(([key, label, placeholder]) => (
            <div key={key}>
              <label className="text-xs text-gray-600">{label}</label>
              <input
                type={['year','mileage_current'].includes(key) ? 'number' : 'text'}
                value={form[key]}
                onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                placeholder={placeholder}
                className="w-full border rounded px-2 py-1.5"
                required={['name','plate','mileage_current'].includes(key)}
              />
            </div>
          ))}
          <div className="col-span-2 md:col-span-3">
            <label className="text-xs text-gray-600">Нотатки</label>
            <input type="text" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
              className="w-full border rounded px-2 py-1.5" />
          </div>
          <div className="col-span-2 md:col-span-3 flex gap-2">
            <button type="submit" className="bg-blue-600 text-white px-4 py-1.5 rounded-lg hover:bg-blue-700">Додати</button>
            <button type="button" onClick={() => setShowAdd(false)} className="text-gray-500 hover:text-gray-700 text-sm">Скасувати</button>
          </div>
        </form>
      )}

      {vehicles.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-3">🚐</div>
          <p>Автомобілів ще немає. Додайте перший!</p>
        </div>
      ) : (
        vehicles.map(v => (
          <VehicleCard key={v.id} v={v} onUpdated={load} onDeleted={deleteVehicle} />
        ))
      )}
    </div>
  )
}
