import { useState } from 'react'

const WORK_TYPES = {
  oil_change:   'Заміна масла',
  brake_pads:   'Гальмівні колодки',
  timing_belt:  'ГРМ',
  tires:        'Шини',
  filters:      'Фільтри',
  battery:      'АКБ',
  other:        'Інше',
}

function Field({ label, children, hint }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  )
}

function NumInput({ value, onChange, min = 0, step = 1, placeholder }) {
  return (
    <input
      type="number"
      min={min}
      step={step}
      value={value}
      onChange={e => onChange(Number(e.target.value))}
      placeholder={placeholder}
      className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
    />
  )
}

function ResultRow({ label, value, bold, color }) {
  return (
    <div className={`flex justify-between py-2 border-b last:border-0 ${bold ? 'font-bold text-base' : 'text-sm'}`}>
      <span className="text-gray-600">{label}</span>
      <span className={color || (value >= 0 ? 'text-gray-900' : 'text-red-600')}>
        {typeof value === 'number'
          ? `${value >= 0 ? '' : ''}${value.toFixed(2)} €`
          : value}
      </span>
    </div>
  )
}

export default function Profitability() {
  const [form, setForm] = useState({
    distance:         1500,   // km (one way UA→CZ)
    pax_go:           8,
    pax_return:       8,
    price_per_seat:   60,     // €
    fuel_l100:        11,     // L/100km
    fuel_price:       1.65,   // €/L
    tolls:            40,     // €
    driver_salary:    150,    // €
  })

  const set = (key, val) => setForm(f => ({ ...f, [key]: val }))

  // Calculations
  const total_distance  = form.distance * 2                         // round trip km
  const fuel_liters     = (total_distance * form.fuel_l100) / 100
  const fuel_cost       = fuel_liters * form.fuel_price
  const total_pax       = form.pax_go + form.pax_return
  const revenue         = total_pax * form.price_per_seat
  const total_costs     = fuel_cost + form.tolls + form.driver_salary
  const profit          = revenue - total_costs
  const margin          = revenue > 0 ? (profit / revenue) * 100 : 0

  const profitColor =
    profit > 0 ? 'text-green-600' : profit < 0 ? 'text-red-600' : 'text-gray-900'

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Рентабельність рейсу</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* ── Inputs ── */}
        <div className="bg-white rounded-xl shadow p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-700 border-b pb-2">Параметри рейсу</h2>

          <Field label="Відстань (в один бік, км)" hint="Наприклад: Рівне → Прага ≈ 1 500 км">
            <NumInput value={form.distance} onChange={v => set('distance', v)} min={1} />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Пасажири туди (макс. 8)">
              <NumInput value={form.pax_go} onChange={v => set('pax_go', Math.min(8, v))} min={0} />
            </Field>
            <Field label="Пасажири назад (макс. 8)">
              <NumInput value={form.pax_return} onChange={v => set('pax_return', Math.min(8, v))} min={0} />
            </Field>
          </div>

          <Field label="Ціна за місце (€)">
            <NumInput value={form.price_per_seat} onChange={v => set('price_per_seat', v)} min={0} step={5} />
          </Field>

          <h2 className="text-lg font-semibold text-gray-700 border-b pb-2 pt-2">Витрати</h2>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Розхід палива (л/100 км)">
              <NumInput value={form.fuel_l100} onChange={v => set('fuel_l100', v)} min={1} step={0.5} />
            </Field>
            <Field label="Ціна палива (€/л)">
              <NumInput value={form.fuel_price} onChange={v => set('fuel_price', v)} min={0} step={0.01} />
            </Field>
          </div>

          <Field label="Дорожні збори / vignette (€)" hint="Автобани CZ, SK, вантажні і т.д.">
            <NumInput value={form.tolls} onChange={v => set('tolls', v)} min={0} step={5} />
          </Field>

          <Field label="Зарплата водія (€)">
            <NumInput value={form.driver_salary} onChange={v => set('driver_salary', v)} min={0} step={10} />
          </Field>
        </div>

        {/* ── Results ── */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="text-lg font-semibold text-gray-700 border-b pb-2 mb-3">Розрахунок</h2>

            <ResultRow label="Пасажирів всього" value={`${total_pax} осіб`} color="text-gray-900" />
            <ResultRow label="Пробіг туди-назад" value={`${total_distance.toLocaleString()} км`} color="text-gray-900" />
            <ResultRow label="Витрата палива" value={`${fuel_liters.toFixed(1)} л`} color="text-gray-900" />

            <div className="my-3 border-t" />

            <ResultRow label="Виручка" value={revenue} color="text-blue-700" />
            <ResultRow label="  → паливо" value={-fuel_cost} />
            <ResultRow label="  → дорожні збори" value={-form.tolls} />
            <ResultRow label="  → зарплата водія" value={-form.driver_salary} />
            <ResultRow label="Витрати всього" value={-total_costs} />

            <div className="my-3 border-t" />

            <ResultRow label="Прибуток" value={profit} bold color={profitColor} />
            <div className={`flex justify-between py-2 font-bold text-base`}>
              <span className="text-gray-600">Рентабельність</span>
              <span className={profitColor}>{margin.toFixed(1)} %</span>
            </div>
          </div>

          {/* Status badge */}
          <div className={`rounded-xl p-4 text-center font-semibold text-lg ${
            profit > 0
              ? 'bg-green-50 text-green-700 border border-green-200'
              : profit < 0
              ? 'bg-red-50 text-red-700 border border-red-200'
              : 'bg-gray-50 text-gray-600 border border-gray-200'
          }`}>
            {profit > 0 ? `Рейс прибутковий (+${profit.toFixed(2)} €)` :
             profit < 0 ? `Рейс збитковий (${profit.toFixed(2)} €)` :
             'Рейс в нуль'}
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-700">
            <strong>Підказка:</strong> при повному завантаженні (8+8 = 16 пасажирів) мінімальна беззбиткова ціна за місце:
            <span className="font-bold ml-1">
              {total_pax > 0 ? (total_costs / total_pax).toFixed(2) : '—'} €
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
