import { useEffect, useState } from 'react'
import {
  getParcels, createParcel, updateParcelStatus, deleteParcel,
  uploadParcelPhoto, parcelPhotoUrl,
} from '../api'

const EMPTY_FORM = {
  direction: 'UA->CZ',
  sender: '',
  sender_phone: '',
  sender_address: '',
  receiver: '',
  receiver_phone: '',
  receiver_address: '',
  np_office: '',
  description: '',
  price: '',
}

const STATUSES = [
  { value: 'accepted',         label: 'Прийнято',        color: 'bg-yellow-100 text-yellow-700' },
  { value: 'in_transit',       label: 'В дорозі',        color: 'bg-blue-100 text-blue-700' },
  { value: 'border_crossed',   label: 'Перетнула кордон', color: 'bg-indigo-100 text-indigo-700' },
  { value: 'out_for_delivery', label: 'Сьогодні доставка', color: 'bg-orange-100 text-orange-700' },
  { value: 'delivered',        label: 'Доставлено',      color: 'bg-green-100 text-green-700' },
]

const STATUS_COLOR = Object.fromEntries(STATUSES.map((s) => [s.value, s.color]))

export default function ParcelsPage() {
  const [parcels, setParcels]   = useState([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState(EMPTY_FORM)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')
  const [photoFile, setPhotoFile] = useState(null)

  const load = async () => {
    const res = await getParcels()
    setParcels(res.data)
  }

  useEffect(() => { load() }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const payload = { ...form, price: form.price ? Number(form.price) : null }
      const { data: parcel } = await createParcel(payload)
      if (photoFile) await uploadParcelPhoto(parcel.id, photoFile)
      setShowForm(false)
      setForm(EMPTY_FORM)
      setPhotoFile(null)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Помилка збереження')
    } finally {
      setLoading(false)
    }
  }

  const handleStatusChange = async (id, status) => {
    await updateParcelStatus(id, status)
    load()
  }

  const handleDelete = async (id) => {
    if (!confirm('Видалити посилку?')) return
    await deleteParcel(id)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Посилки</h1>
        <button
          onClick={() => { setForm(EMPTY_FORM); setPhotoFile(null); setError(''); setShowForm(true) }}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          + Нова посилка
        </button>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 text-left">Трек</th>
              <th className="px-4 py-3 text-left">Напрямок</th>
              <th className="px-4 py-3 text-left">Відправник</th>
              <th className="px-4 py-3 text-left">Отримувач</th>
              <th className="px-4 py-3 text-left">Доставка</th>
              <th className="px-4 py-3 text-left">Фото</th>
              <th className="px-4 py-3 text-left">Дата</th>
              <th className="px-4 py-3 text-left">Статус</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {parcels.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-8 text-gray-400">
                  Посилок ще немає
                </td>
              </tr>
            )}
            {parcels.map((p) => (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs font-medium">{p.tracking_number}</td>
                <td className="px-4 py-3">
                  <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-xs font-medium">
                    {p.direction}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium">{p.sender}</div>
                  <div className="text-xs text-gray-400">{p.sender_phone}</div>
                  {p.sender_address && <div className="text-xs text-gray-400">{p.sender_address}</div>}
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium">{p.receiver}</div>
                  <div className="text-xs text-gray-400">{p.receiver_phone}</div>
                </td>
                <td className="px-4 py-3 text-gray-600 max-w-xs">
                  {p.receiver_address || p.np_office || '—'}
                  {p.description && <div className="text-xs text-gray-400 truncate">{p.description}</div>}
                </td>
                <td className="px-4 py-3">
                  {p.photos?.length ? (
                    <a href={parcelPhotoUrl(p.photos[0].filename)} target="_blank" rel="noreferrer">
                      <img
                        src={parcelPhotoUrl(p.photos[0].filename)}
                        alt="Фото посилки"
                        className="w-12 h-12 object-cover rounded border"
                      />
                    </a>
                  ) : (
                    <span className="text-gray-300 text-xs">немає</span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs">
                  {new Date(p.created_at).toLocaleDateString('uk-UA')}
                </td>
                <td className="px-4 py-3">
                  <select
                    className={`text-xs font-medium rounded px-2 py-1 border-0 focus:outline-none cursor-pointer ${STATUS_COLOR[p.status]}`}
                    value={p.status}
                    onChange={(e) => handleStatusChange(p.id, e.target.value)}
                  >
                    {STATUSES.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleDelete(p.id)}
                    className="text-red-400 hover:text-red-600 text-sm"
                  >
                    Видалити
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal form */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b">
              <h2 className="text-lg font-bold">Нова посилка</h2>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-700 text-xl">✕</button>
            </div>

            <form onSubmit={handleSubmit} className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Напрямок</label>
                <select
                  className="w-full border rounded-lg px-3 py-2 text-sm"
                  value={form.direction}
                  onChange={(e) => setForm({ ...form, direction: e.target.value })}
                >
                  <option value="UA->CZ">UA → CZ</option>
                  <option value="CZ->UA">CZ → UA</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Відправник (ПІБ)</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.sender}
                    onChange={(e) => setForm({ ...form, sender: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Телефон відправника</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="+380XXXXXXXXX"
                    value={form.sender_phone}
                    onChange={(e) => setForm({ ...form, sender_phone: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Отримувач (ПІБ)</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={form.receiver}
                    onChange={(e) => setForm({ ...form, receiver: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Телефон отримувача</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="+380XXXXXXXXX"
                    value={form.receiver_phone}
                    onChange={(e) => setForm({ ...form, receiver_phone: e.target.value })}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Адреса забору</label>
                <input
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Рівне, вул. Соборна 12"
                  value={form.sender_address}
                  onChange={(e) => setForm({ ...form, sender_address: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Адреса доставки</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Praha, Vinohradská 25"
                    value={form.receiver_address}
                    onChange={(e) => setForm({ ...form, receiver_address: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">…або відділення НП</label>
                  <input
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Відділення №5, м. Рівне"
                    value={form.np_office}
                    onChange={(e) => setForm({ ...form, np_office: e.target.value })}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Опис вантажу</label>
                  <textarea
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={3}
                    placeholder="Що веземо?"
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Ціна</label>
                    <input
                      type="number"
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={form.price}
                      onChange={(e) => setForm({ ...form, price: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Фото посилки</label>
                    <input
                      type="file"
                      accept="image/*"
                      className="w-full text-xs"
                      onChange={(e) => setPhotoFile(e.target.files[0] || null)}
                    />
                  </div>
                </div>
              </div>

              {error && <p className="text-red-500 text-sm">{error}</p>}

              <div className="flex gap-3 justify-end pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 border rounded-lg text-sm hover:bg-gray-50"
                >
                  Скасувати
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  {loading ? 'Збереження...' : 'Зберегти'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
