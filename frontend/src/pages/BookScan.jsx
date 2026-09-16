import { useEffect, useState } from 'react'
import { getRides, importBookPage, scanBookPage } from '../api'

const fmtDate = (iso) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('uk-UA', { weekday: 'short', day: 'numeric', month: 'long' })

const DIRECTION_NAME = { 'UA->CZ': 'Україна → Чехія', 'CZ->UA': 'Чехія → Україна' }

// A photographed page of the book becomes an editable table. Nothing is saved
// until the person who knows the handwriting has looked it over.
export default function BookScanPage() {
  const [rides, setRides]     = useState([])
  const [file, setFile]       = useState(null)
  const [preview, setPreview] = useState(null)
  const [busy, setBusy]       = useState(false)
  const [scan, setScan]       = useState(null)
  const [rows, setRows]       = useState([])
  const [rideId, setRideId]   = useState('')
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState(null)

  useEffect(() => { getRides().then((r) => setRides(r.data)) }, [])

  const pick = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setScan(null); setRows([]); setResult(null); setError(null)
  }

  const runScan = async () => {
    if (!file) return
    setBusy(true); setError(null); setResult(null)
    try {
      const res = await scanBookPage(file)
      setScan(res.data)
      setRows(res.data.page.rows.map((r) => ({ ...r, include: !r.crossed_out })))
      setRideId(res.data.ride?.id ? String(res.data.ride.id) : '')
    } catch (err) {
      setError(err.response?.data?.detail || 'Не вдалося прочитати сторінку')
    } finally {
      setBusy(false)
    }
  }

  const edit = (i, key, value) => setRows((prev) => prev.map((r, j) => (j === i ? { ...r, [key]: value } : r)))
  const removeRow = (i) => setRows((prev) => prev.filter((_, j) => j !== i))
  const addRow = () => setRows((prev) => [...prev, {
    line_no: prev.length + 1, running_total: null, seats: 1, from_city: '', to_city: '',
    phone: '', price: null, note: '', crossed_out: false, uncertain: false, raw: '', include: true,
  }])

  const doImport = async () => {
    const chosen = rows.filter((r) => r.include)
    if (!rideId || !chosen.length) return
    setBusy(true); setError(null)
    try {
      const res = await importBookPage({
        ride_id: Number(rideId),
        rows: chosen.map((r) => ({
          from_city: r.from_city, to_city: r.to_city, phone: r.phone || null,
          seats: Number(r.seats) || 1, note: r.note || null, price: r.price || null,
        })),
      })
      setResult(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Не вдалося імпортувати')
    } finally {
      setBusy(false)
    }
  }

  const today = new Date().toISOString().slice(0, 10)
  // upcoming rides, plus whichever one the page itself points at (a page from
  // last week is still a page someone may need to import)
  const rideOptions = rides
    .filter((r) => r.status === 'active' && (r.date >= today || r.id === scan?.ride?.id))
    .sort((a, b) => a.date.localeCompare(b.date))

  const total = rows.filter((r) => r.include).reduce((s, r) => s + (Number(r.seats) || 0), 0)
  const cell = 'border rounded px-2 py-1 w-full text-sm'

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Сторінка зошита</h1>
      <p className="text-gray-500 mb-6 max-w-2xl">
        Сфотографуйте сторінку — рядки розпізнаються в таблицю. Перевірте жовті рядки, поправте, що треба,
        і імпортуйте. Записи, чий телефон уже є на рейсі, не подвояться — вони просто позначаться «у книжці».
      </p>

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <label className="bg-white border rounded-lg px-4 py-2 cursor-pointer hover:bg-gray-50">
          {file ? file.name : 'Обрати фото'}
          <input type="file" accept="image/*" capture="environment" onChange={pick} className="hidden" />
        </label>
        <button onClick={runScan} disabled={!file || busy}
                className="bg-blue-700 hover:bg-blue-800 disabled:opacity-50 text-white rounded-lg px-4 py-2">
          {busy && !scan ? 'Читаю… (до 2 хв)' : 'Розпізнати'}
        </button>
      </div>

      {error && <div className="bg-red-50 text-red-700 rounded-lg px-3 py-2 mb-4">{error}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(280px,1fr)_minmax(0,2fr)] gap-6 items-start">
        {preview && (
          <img src={preview} alt="сторінка зошита" className="rounded-lg shadow-sm w-full sticky top-4" />
        )}

        {scan && (
          <div>
            <div className="bg-white rounded-lg shadow-sm p-4 mb-4 flex flex-wrap items-center gap-3">
              <div className="text-sm text-gray-500">
                Сторінка: <b>{scan.page.day}.{scan.page.month}</b> {scan.page.weekday}
                {scan.direction && <> · {DIRECTION_NAME[scan.direction]}</>}
              </div>
              <select value={rideId} onChange={(e) => setRideId(e.target.value)} className="border rounded-lg px-3 py-2">
                <option value="">— оберіть рейс —</option>
                {rideOptions.map((r) => (
                  <option key={r.id} value={r.id}>{fmtDate(r.date)} · {r.route.name}</option>
                ))}
              </select>
              {scan.page.margin_notes?.length > 0 && (
                <div className="text-sm text-amber-700">На полях: {scan.page.margin_notes.join('; ')}</div>
              )}
            </div>

            <table className="w-full bg-white rounded-lg shadow-sm text-sm">
              <thead>
                <tr className="text-left text-gray-500">
                  <th className="p-2 w-8"></th>
                  <th className="p-2 w-10">№</th>
                  <th className="p-2 w-16">Місць</th>
                  <th className="p-2">Звідки</th>
                  <th className="p-2">Куди</th>
                  <th className="p-2">Телефон</th>
                  <th className="p-2">Примітка</th>
                  <th className="p-2 w-8"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className={`border-t ${!r.include ? 'opacity-40' : r.uncertain ? 'bg-amber-50' : ''}`}>
                    <td className="p-2"><input type="checkbox" checked={r.include} onChange={(e) => edit(i, 'include', e.target.checked)} /></td>
                    <td className="p-2 text-gray-400">{r.running_total ?? '·'}{r.crossed_out ? ' ✗' : ''}</td>
                    <td className="p-2"><input type="number" min="1" max="8" value={r.seats ?? ''} onChange={(e) => edit(i, 'seats', e.target.value)} className={cell} /></td>
                    <td className="p-2"><input value={r.from_city} onChange={(e) => edit(i, 'from_city', e.target.value)} className={cell} /></td>
                    <td className="p-2"><input value={r.to_city} onChange={(e) => edit(i, 'to_city', e.target.value)} className={cell} /></td>
                    <td className="p-2"><input value={r.phone || ''} onChange={(e) => edit(i, 'phone', e.target.value)} className={cell} /></td>
                    <td className="p-2"><input value={[r.price, r.note].filter(Boolean).join(' ')} onChange={(e) => { edit(i, 'note', e.target.value); edit(i, 'price', null) }} className={cell} /></td>
                    <td className="p-2"><button onClick={() => removeRow(i)} className="text-gray-400 hover:text-red-600">✕</button></td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="flex flex-wrap items-center gap-3 mt-4">
              <button onClick={addRow} className="text-sm text-blue-700 hover:underline">+ рядок</button>
              <div className="text-sm text-gray-500 ml-auto">
                До імпорту: <b>{rows.filter((r) => r.include).length}</b> записів, <b>{total}</b> місць
                {total > 8 && <> · {Math.ceil(total / 8)} буси</>}
              </div>
              <button onClick={doImport} disabled={busy || !rideId || !rows.some((r) => r.include)}
                      className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg px-5 py-2">
                {busy ? 'Імпортую…' : 'Імпортувати'}
              </button>
            </div>

            {result && (
              <div className="mt-4 bg-green-50 text-green-800 rounded-lg px-4 py-3">
                Створено {result.created}, збіглося з наявними {result.matched}.
                {result.skipped.length > 0 && <> Пропущено: {result.skipped.join('; ')}</>}
                {' '}<a href={`/admin/split?ride=${rideId}`} className="underline font-medium">Розподілити по бусах →</a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
