import axios from 'axios'

const api = axios.create({ baseURL: '/' })

// Attach JWT token to every request if present
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Redirect to login on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login = (username, password) => {
  const form = new URLSearchParams()
  form.append('username', username)
  form.append('password', password)
  return api.post('/auth/token', form)
}

// ── Routes ────────────────────────────────────────────────────────────────────
export const getRoutes  = ()          => api.get('/api/routes')
export const getRoute   = (id)        => api.get(`/api/routes/${id}`)
export const createRoute = (data)     => api.post('/api/routes', data)
export const updateRoute = (id, data) => api.put(`/api/routes/${id}`, data)
export const deleteRoute = (id)       => api.delete(`/api/routes/${id}`)

// ── Rides ─────────────────────────────────────────────────────────────────────
export const getRides   = ()          => api.get('/api/rides')
export const createRide = (data)      => api.post('/api/rides', data)
export const deleteRide = (id)        => api.delete(`/api/rides/${id}`)
export const getRideBookings = (id)   => api.get(`/api/rides/${id}/bookings`)
export const assignDriver = (rideId, driverId) =>
  api.patch(`/api/rides/${rideId}/assign-driver`, null, { params: driverId ? { driver_id: driverId } : {} })

// ── Users / drivers ───────────────────────────────────────────────────────────
export const getUsers   = ()          => api.get('/api/users')
export const createUser = (data)      => api.post('/api/users', data)
export const updateUser = (id, data)  => api.patch(`/api/users/${id}`, data)
export const deleteUser = (id)        => api.delete(`/api/users/${id}`)

// ── Bookings ──────────────────────────────────────────────────────────────────
export const getBookings    = (phone) => api.get('/api/bookings', { params: phone ? { phone } : {} })
export const createBooking  = (data)  => api.post('/api/bookings', data)
export const updateBooking  = (id, data) => api.patch(`/api/bookings/${id}`, data)
export const cancelBooking  = (id)    => api.delete(`/api/bookings/${id}`)
export const getBookQueue   = ()      => api.get('/api/bookings', { params: { book_status: 'pending' } })
export const searchBookings = (phone) => api.get('/api/bookings', { params: { phone } })
export const markWrittenInBook = (id) => api.patch(`/api/bookings/${id}/book`)

// ── Parcels ───────────────────────────────────────────────────────────────────
export const getParcels     = (params) => api.get('/api/parcels', { params })
export const createParcel   = (data)  => api.post('/api/parcels', data)
export const updateParcel   = (id, data) => api.patch(`/api/parcels/${id}`, data)
export const updateParcelStatus = (id, status) => api.patch(`/api/parcels/${id}/status`, { status })
export const deleteParcel   = (id)    => api.delete(`/api/parcels/${id}`)
export const uploadParcelPhoto = (id, file, kind = 'intake') => {
  const form = new FormData()
  form.append('file', file)
  return api.post(`/api/parcels/${id}/photos`, form, { params: { kind } })
}
export const parcelPhotoUrl = (filename) => `/media/parcels/${filename}`
