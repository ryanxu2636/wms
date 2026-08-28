import http from './http'

export const listSkus = (params) => http.get('/sku', { params })
export const createSku = (data) => http.post('/sku', data)
export const updateSku = (id, data) => http.patch(`/sku/${id}`, data)
export const createBom = (data) => http.post('/sku/bom', data)
export const getBom = (id) => http.get(`/sku/${id}/bom`)

export const listRules = () => http.get('/rules')
export const createRule = (data) => http.post('/rules', data)
export const deleteRule = (id) => http.delete(`/rules/${id}`)

export const listWarehouses = () => http.get('/warehouse')
export const createWarehouse = (data) => http.post('/warehouse', data)
export const createShelf = (data) => http.post('/warehouse/shelf', data)
export const createLocation = (data) => http.post('/warehouse/location', data)
export const listLocations = (params) => http.get('/warehouse/location', { params })

export const previewImport = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post('/import/preview', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export const commitImport = (file, overwrite = false) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post(`/import/commit?overwrite=${overwrite}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export const listBatches = () => http.get('/import/batches')
export const listReviews = (status) => http.get('/import/review', { params: { status } })
export const resolveReview = (id, resolution, status = '已处理') =>
  http.post(`/import/review/${id}/resolve?resolution=${encodeURIComponent(resolution)}&status=${status}`)
