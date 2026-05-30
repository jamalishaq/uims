import api from '../../lib/api'

export const login = (credentials) =>
  api.post('/auth/login', credentials).then((r) => r.data)

export const logout = () =>
  api.post('/auth/logout').then((r) => r.data)
