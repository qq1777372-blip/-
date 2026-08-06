import http from './http'
import type {
  AccountUsageRecord,
  AccountUsagePasswordRevealPayload,
  AccountUsageAccountNameRevealResponse,
  AccountUsageBatchStatusPayload,
  AccountUsagePasswordRevealResponse,
  AccountUsageRecordPayload,
  AdminSessionInfo,
  AdminUser,
  AdminUserAccessPayload,
  AdminUserCreatePayload,
  AdminUserPasswordResetPayload,
  AdminUserStatusPayload,
  AuditLog,
  BatchActionResult,
  BatchDeletePayload,
  ChangePasswordPayload,
  CurrentUser,
  CurrentUserProfilePayload,
  CustomFieldCreatePayload,
  CustomFieldReorderPayload,
  CustomFieldUpdatePayload,
  CustomField,
  DashboardStats,
  ServerStatus,
  DingTalkProfitMonthlySummary,
  DingTalkProfitRecord,
  DingTalkProfitSummary,
  GlobalSearchResponse,
  LicenseRecord,
  LicenseRecordPayload,
  LoginCaptcha,
  MobileDeviceRecord,
  MobileDeviceRecordPayload,
  PeerShop,
  PeerShopPayload,
  LoginPayload,
  ShopRecord,
  ShopRecordPayload,
  SavedLink,
  SavedLinkPayload,
  SavedLinkPushPayload,
  SoftwareAdminUser,
  TaskBookkeepingBatchActionResult,
  TaskBookkeepingBatchDeletePayload,
  TaskBookkeepingBatchStatusPayload,
  TaskBookkeepingOwner,
  TaskBookkeepingOwnerPayload,
  TaskBookkeepingRecord,
  TaskBookkeepingRecordPayload,
  TaskBookkeepingShop,
  TaskBookkeepingShopPayload,
  TaskBookkeepingSummary,
  TotpSetupResponse,
  SystemAlertList,
  SystemSettings,
} from '../types/api'

export async function fetchCurrentUser() {
  const { data } = await http.get<CurrentUser>('/auth/me')
  return data
}

export async function fetchLoginCaptcha() {
  const { data } = await http.get<LoginCaptcha>('/auth/captcha', {
    headers: {
      'Cache-Control': 'no-cache',
    },
  })
  return data
}

export async function login(payload: LoginPayload) {
  const { data } = await http.post<CurrentUser>('/auth/login', payload)
  return data
}

export async function logout() {
  await http.post('/auth/logout')
}

export async function fetchAuthSessions() {
  const { data } = await http.get<AdminSessionInfo[]>('/auth/sessions')
  return data
}

export async function revokeAuthSession(sessionId: number) {
  await http.delete(`/auth/sessions/${sessionId}`)
}

export async function revokeOtherAuthSessions() {
  const { data } = await http.post<BatchActionResult>('/auth/sessions/revoke-others')
  return data
}

export async function changePassword(payload: ChangePasswordPayload) {
  const { data } = await http.post<CurrentUser>('/auth/change-password', payload)
  return data
}

export async function setupTotp(currentPassword: string) {
  const { data } = await http.post<TotpSetupResponse>('/auth/totp/setup', {
    current_password: currentPassword,
  })
  return data
}

export async function confirmTotp(secret: string, code: string) {
  const { data } = await http.post<CurrentUser>('/auth/totp/confirm', { secret, code })
  return data
}

export async function disableTotp(currentPassword: string, code: string) {
  const { data } = await http.post<CurrentUser>('/auth/totp/disable', {
    current_password: currentPassword,
    code,
  })
  return data
}

export async function updateCurrentUserProfile(payload: CurrentUserProfilePayload) {
  const { data } = await http.patch<CurrentUser>('/auth/profile', payload)
  return data
}

export async function uploadCurrentUserAvatar(file: File) {
  const formData = new FormData()
  formData.append('image', file)

  const { data } = await http.post<CurrentUser>('/auth/avatar', formData)
  return data
}

export async function deleteCurrentUserAvatar() {
  const { data } = await http.delete<CurrentUser>('/auth/avatar')
  return data
}

export async function fetchDashboardStats() {
  const { data } = await http.get<DashboardStats>('/dashboard/stats')
  return data
}

export async function fetchSystemAlerts(category = '', statusFilter = 'all') {
  const { data } = await http.get<SystemAlertList>('/system-alerts', {
    params: { category: category || undefined, status_filter: statusFilter },
  })
  return data
}

export async function updateSystemAlertStatus(alertKey: string, acknowledged: boolean) {
  const { data } = await http.patch<SystemAlertList>(`/system-alerts/${encodeURIComponent(alertKey)}`, { acknowledged })
  return data
}

export async function fetchSystemSettings() {
  const { data } = await http.get<SystemSettings>('/system-settings')
  return data
}

export async function saveSystemSettings(payload: SystemSettings) {
  const { data } = await http.put<SystemSettings>('/system-settings', payload)
  return data
}

export async function fetchServerStatus(refresh = false) {
  const { data } = await http.get<ServerStatus>('/dashboard/server-status', {
    params: refresh ? { refresh: true } : undefined,
  })
  return data
}

export async function fetchDingTalkProfitSummary() {
  const { data } = await http.get<DingTalkProfitSummary>('/dingtalk-profits/summary')
  return data
}

export async function fetchDingTalkProfitMonthlySummary() {
  const { data } = await http.get<DingTalkProfitMonthlySummary[]>('/dingtalk-profits/monthly-summary')
  return data
}

export async function fetchDingTalkProfits() {
  const { data } = await http.get<DingTalkProfitRecord[]>('/dingtalk-profits')
  return data
}

export async function fetchSavedLinks() {
  const { data } = await http.get<SavedLink[]>('/saved-links')
  return data
}

export async function createSavedLink(payload: SavedLinkPayload) {
  const { data } = await http.post<SavedLink>('/saved-links', payload)
  return data
}

export async function updateSavedLink(linkId: number, payload: SavedLinkPayload) {
  const { data } = await http.put<SavedLink>(`/saved-links/${linkId}`, payload)
  return data
}

export async function deleteSavedLink(linkId: number) {
  await http.delete(`/saved-links/${linkId}`)
}

export async function pinSavedLink(linkId: number) {
  const { data } = await http.post<SavedLink>(`/saved-links/${linkId}/pin`)
  return data
}

export async function unpinSavedLink(linkId: number) {
  const { data } = await http.delete<SavedLink>(`/saved-links/${linkId}/pin`)
  return data
}

export async function scheduleSavedLinkPush(linkId: number, payload: SavedLinkPushPayload) {
  const { data } = await http.post<SavedLink>(`/saved-links/${linkId}/push`, payload)
  return data
}

export async function uploadSavedLinkImages(linkId: number, files: File[]) {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('images', file)
  })

  const { data } = await http.post<SavedLink>(`/saved-links/${linkId}/images`, formData)
  return data
}

export async function appendSavedLinkImages(linkId: number, files: File[]) {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('images', file)
  })

  const { data } = await http.post<SavedLink>(`/saved-links/${linkId}/images/append`, formData)
  return data
}

export async function replaceSavedLinkImage(linkId: number, imageName: string, file: File) {
  const formData = new FormData()
  formData.append('image', file)

  const { data } = await http.put<SavedLink>(`/saved-links/${linkId}/images/${encodeURIComponent(imageName)}`, formData)
  return data
}

export async function deleteSavedLinkImage(linkId: number, imageName: string) {
  const { data } = await http.delete<SavedLink>(`/saved-links/${linkId}/images/${encodeURIComponent(imageName)}`)
  return data
}

export async function fetchGlobalSearch(query: string) {
  const { data } = await http.get<GlobalSearchResponse>('/global-search', {
    params: { q: query },
  })
  return data
}

export async function fetchShopRecords() {
  const { data } = await http.get<ShopRecord[]>('/shop-records')
  return data
}

export async function fetchTaskBookkeepingSummary() {
  const { data } = await http.get<TaskBookkeepingSummary>('/task-bookkeeping/summary')
  return data
}

export async function fetchTaskBookkeepingRecords() {
  const { data } = await http.get<TaskBookkeepingRecord[]>('/task-bookkeeping/records')
  return data
}

export async function createTaskBookkeepingRecord(payload: TaskBookkeepingRecordPayload) {
  const { data } = await http.post<TaskBookkeepingRecord>('/task-bookkeeping/records', payload)
  return data
}

export async function updateTaskBookkeepingRecord(
  recordId: number,
  payload: TaskBookkeepingRecordPayload,
) {
  const { data } = await http.put<TaskBookkeepingRecord>(`/task-bookkeeping/records/${recordId}`, payload)
  return data
}

export async function deleteTaskBookkeepingRecord(recordId: number) {
  await http.delete(`/task-bookkeeping/records/${recordId}`)
}

export async function batchUpdateTaskBookkeepingRecordStatus(
  payload: TaskBookkeepingBatchStatusPayload,
) {
  const { data } = await http.patch<TaskBookkeepingBatchActionResult>(
    '/task-bookkeeping/records/batch-status',
    payload,
  )
  return data
}

export async function batchDeleteTaskBookkeepingRecords(payload: TaskBookkeepingBatchDeletePayload) {
  const { data } = await http.post<TaskBookkeepingBatchActionResult>(
    '/task-bookkeeping/records/batch-delete',
    payload,
  )
  return data
}

export async function fetchTaskBookkeepingShops() {
  const { data } = await http.get<TaskBookkeepingShop[]>('/task-bookkeeping/shops')
  return data
}

export async function createTaskBookkeepingShop(payload: TaskBookkeepingShopPayload) {
  const { data } = await http.post<TaskBookkeepingShop>('/task-bookkeeping/shops', payload)
  return data
}

export async function deleteTaskBookkeepingShop(shopId: number) {
  await http.delete(`/task-bookkeeping/shops/${shopId}`)
}

export async function fetchTaskBookkeepingOwners() {
  const { data } = await http.get<TaskBookkeepingOwner[]>('/task-bookkeeping/owners')
  return data
}

export async function createTaskBookkeepingOwner(payload: TaskBookkeepingOwnerPayload) {
  const { data } = await http.post<TaskBookkeepingOwner>('/task-bookkeeping/owners', payload)
  return data
}

export async function deleteTaskBookkeepingOwner(ownerId: number) {
  await http.delete(`/task-bookkeeping/owners/${ownerId}`)
}

export async function createShopRecord(payload: ShopRecordPayload) {
  const { data } = await http.post<ShopRecord>('/shop-records', payload)
  return data
}

export async function updateShopRecord(recordId: number, payload: ShopRecordPayload) {
  const { data } = await http.put<ShopRecord>(`/shop-records/${recordId}`, payload)
  return data
}

export async function deleteShopRecord(recordId: number) {
  await http.delete(`/shop-records/${recordId}`)
}

export async function batchDeleteShopRecords(payload: BatchDeletePayload) {
  const { data } = await http.post<BatchActionResult>('/shop-records/batch-delete', payload)
  return data
}

export async function fetchCustomFields() {
  const { data } = await http.get<CustomField[]>('/custom-fields')
  return data
}

export async function fetchUiSetting<T>(settingKey: string) {
  const { data } = await http.get<{ key: string; value: T | null }>(`/ui-settings/${settingKey}`)
  return data.value
}

export async function saveUiSetting<T>(settingKey: string, value: T) {
  const { data } = await http.put<{ key: string; value: T }>(`/ui-settings/${settingKey}`, { value })
  return data.value
}

export async function createCustomField(payload: CustomFieldCreatePayload) {
  const { data } = await http.post<CustomField>('/custom-fields', payload)
  return data
}

export async function updateCustomField(fieldId: number, payload: CustomFieldUpdatePayload) {
  const { data } = await http.patch<CustomField>(`/custom-fields/${fieldId}`, payload)
  return data
}

export async function reorderCustomFields(payload: CustomFieldReorderPayload) {
  const { data } = await http.post<CustomField[]>('/custom-fields/reorder', payload)
  return data
}

export async function deleteCustomField(fieldId: number) {
  await http.delete(`/custom-fields/${fieldId}`)
}

export async function fetchLicenseRecords() {
  const { data } = await http.get<LicenseRecord[]>('/license-records')
  return data
}

export async function createLicenseRecord(payload: LicenseRecordPayload) {
  const { data } = await http.post<LicenseRecord>('/license-records', payload)
  return data
}

export async function updateLicenseRecord(recordId: number, payload: LicenseRecordPayload) {
  const { data } = await http.put<LicenseRecord>(`/license-records/${recordId}`, payload)
  return data
}

export async function deleteLicenseRecord(recordId: number) {
  await http.delete(`/license-records/${recordId}`)
}

export async function batchDeleteLicenseRecords(payload: BatchDeletePayload) {
  const { data } = await http.post<BatchActionResult>('/license-records/batch-delete', payload)
  return data
}

export async function uploadLicenseImage(recordId: number, file: File) {
  const formData = new FormData()
  formData.append('image', file)

  const { data } = await http.post<LicenseRecord>(`/license-records/${recordId}/image`, formData)

  return data
}

export async function deleteLicenseImage(recordId: number) {
  const { data } = await http.delete<LicenseRecord>(`/license-records/${recordId}/image`)
  return data
}

export async function fetchPeerShops() {
  const { data } = await http.get<PeerShop[]>('/peer-shops')
  return data
}

export async function createPeerShop(payload: PeerShopPayload) {
  const { data } = await http.post<PeerShop>('/peer-shops', payload)
  return data
}

export async function updatePeerShop(recordId: number, payload: PeerShopPayload) {
  const { data } = await http.put<PeerShop>(`/peer-shops/${recordId}`, payload)
  return data
}

export async function deletePeerShop(recordId: number) {
  await http.delete(`/peer-shops/${recordId}`)
}

export async function batchDeletePeerShops(payload: BatchDeletePayload) {
  const { data } = await http.post<BatchActionResult>('/peer-shops/batch-delete', payload)
  return data
}

export async function uploadPeerShopImage(recordId: number, file: File) {
  const formData = new FormData()
  formData.append('image', file)

  const { data } = await http.post<PeerShop>(`/peer-shops/${recordId}/image`, formData)
  return data
}

export async function deletePeerShopImage(recordId: number) {
  const { data } = await http.delete<PeerShop>(`/peer-shops/${recordId}/image`)
  return data
}

export async function fetchAccountUsageRecords() {
  const { data } = await http.get<AccountUsageRecord[]>('/account-usage-records')
  return data
}

export async function fetchAccountUsageRecordForEdit(recordId: number) {
  const { data } = await http.get<AccountUsageRecord>(`/account-usage-records/${recordId}/edit-detail`)
  return data
}

export async function createAccountUsageRecord(payload: AccountUsageRecordPayload) {
  const { data } = await http.post<AccountUsageRecord>('/account-usage-records', payload)
  return data
}

export async function updateAccountUsageRecord(recordId: number, payload: AccountUsageRecordPayload) {
  const { data } = await http.put<AccountUsageRecord>(`/account-usage-records/${recordId}`, payload)
  return data
}

export async function deleteAccountUsageRecord(recordId: number) {
  await http.delete(`/account-usage-records/${recordId}`)
}

export async function batchUpdateAccountUsageStatus(payload: AccountUsageBatchStatusPayload) {
  const { data } = await http.patch<BatchActionResult>('/account-usage-records/batch-status', payload)
  return data
}

export async function batchDeleteAccountUsageRecords(payload: BatchDeletePayload) {
  const { data } = await http.post<BatchActionResult>('/account-usage-records/batch-delete', payload)
  return data
}

export async function revealAccountUsagePassword(
  recordId: number,
  payload: AccountUsagePasswordRevealPayload,
) {
  const { data } = await http.post<AccountUsagePasswordRevealResponse>(
    `/account-usage-records/${recordId}/reveal-password`,
    payload,
  )
  return data
}

export async function revealAccountUsageAccountName(
  recordId: number,
  payload: AccountUsagePasswordRevealPayload,
) {
  const { data } = await http.post<AccountUsageAccountNameRevealResponse>(
    `/account-usage-records/${recordId}/reveal-account-name`,
    payload,
  )
  return data
}

export async function fetchMobileDevices() {
  const { data } = await http.get<MobileDeviceRecord[]>('/mobile-devices')
  return data
}

export async function createMobileDevice(payload: MobileDeviceRecordPayload) {
  const { data } = await http.post<MobileDeviceRecord>('/mobile-devices', payload)
  return data
}

export async function updateMobileDevice(recordId: number, payload: MobileDeviceRecordPayload) {
  const { data } = await http.put<MobileDeviceRecord>(`/mobile-devices/${recordId}`, payload)
  return data
}

export async function deleteMobileDevice(recordId: number) {
  await http.delete(`/mobile-devices/${recordId}`)
}

export async function batchDeleteMobileDevices(payload: BatchDeletePayload) {
  const { data } = await http.post<BatchActionResult>('/mobile-devices/batch-delete', payload)
  return data
}

export async function fetchAdminUsers() {
  const { data } = await http.get<AdminUser[]>('/admin-users')
  return data
}

export async function fetchAuditLogs() {
  const { data } = await http.get<AuditLog[]>('/audit-logs')
  return data
}

export async function createAdminUser(payload: AdminUserCreatePayload) {
  const { data } = await http.post<AdminUser>('/admin-users', payload)
  return data
}

export async function updateAdminUserStatus(userId: number, payload: AdminUserStatusPayload) {
  const { data } = await http.patch<AdminUser>(`/admin-users/${userId}/status`, payload)
  return data
}

export async function updateAdminUserAccess(userId: number, payload: AdminUserAccessPayload) {
  const { data } = await http.patch<AdminUser>(`/admin-users/${userId}`, payload)
  return data
}

export async function resetAdminUserPassword(userId: number, payload: AdminUserPasswordResetPayload) {
  await http.patch(`/admin-users/${userId}/password`, payload)
}

export async function fetchSoftwareAdminUsers() {
  const { data } = await http.get<SoftwareAdminUser[]>('/software-admin/users')
  return data
}

export type LicenseAdminStatus = 'active' | 'disabled' | 'expired'

export interface LicenseAdminDevice {
  device_id: string
  device_name: string | null
  platform: string | null
  app_version: string | null
  bound_at: string
  last_seen_at: string
  last_ip: string | null
}

export interface LicenseAdminItem {
  license_key: string
  plan_name: string
  status: LicenseAdminStatus
  duration_days: number
  max_devices: number
  activated_at: string | null
  expire_at: string | null
  created_at: string
  updated_at: string
  note: string
  feature_flags: Record<string, unknown>
  bound_devices_count: number
  devices: LicenseAdminDevice[]
}

export interface LicenseAdminStats {
  total_licenses: number
  active_licenses: number
  disabled_licenses: number
  bound_devices: number
}

export interface LicenseAdminCreatePayload {
  plan_name: string
  count: number
  duration_days: number
  max_devices: number
  note: string | null
  feature_flags: Record<string, unknown>
}

export interface LicenseAdminStatusPayload {
  status: 'active' | 'disabled'
}

export interface LicenseAdminUnbindPayload {
  device_id: string | null
}

export async function fetchLicenseAdminStats() {
  const { data } = await http.get<LicenseAdminStats>('/license-admin/stats')
  return data
}

export async function fetchLicenseAdminLicenses() {
  const { data } = await http.get<LicenseAdminItem[]>('/license-admin/licenses')
  return data
}

export async function createLicenseAdminLicenses(payload: LicenseAdminCreatePayload) {
  const { data } = await http.post<LicenseAdminItem[]>('/license-admin/licenses', payload)
  return data
}

export async function updateLicenseAdminStatus(licenseKey: string, payload: LicenseAdminStatusPayload) {
  const { data } = await http.post<LicenseAdminItem>(`/license-admin/licenses/${encodeURIComponent(licenseKey)}/status`, payload)
  return data
}

export async function unbindLicenseAdminDevices(licenseKey: string, payload: LicenseAdminUnbindPayload) {
  const { data } = await http.post<LicenseAdminItem>(`/license-admin/licenses/${encodeURIComponent(licenseKey)}/unbind`, payload)
  return data
}

export async function fetchWarehouseSummary() {
  const { data } = await http.get<import('../types/api').WarehouseSummary>('/warehouse/summary')
  return data
}

export async function fetchWarehouses() {
  const { data } = await http.get<import('../types/api').Warehouse[]>('/warehouse/warehouses')
  return data
}

export async function createWarehouse(payload: import('../types/api').WarehousePayload) {
  const { data } = await http.post<import('../types/api').Warehouse>('/warehouse/warehouses', payload)
  return data
}

export async function updateWarehouse(id: number, payload: import('../types/api').WarehousePayload) {
  const { data } = await http.put<import('../types/api').Warehouse>(`/warehouse/warehouses/${id}`, payload)
  return data
}

export async function fetchWarehouseProducts() {
  const { data } = await http.get<import('../types/api').WarehouseProduct[]>('/warehouse/products')
  return data
}

export async function createWarehouseProduct(payload: import('../types/api').WarehouseProductPayload) {
  const { data } = await http.post<import('../types/api').WarehouseProduct>('/warehouse/products', payload)
  return data
}

export async function updateWarehouseProduct(id: number, payload: import('../types/api').WarehouseProductPayload) {
  const { data } = await http.put<import('../types/api').WarehouseProduct>(`/warehouse/products/${id}`, payload)
  return data
}

export async function uploadWarehouseProductImage(id: number, file: File) {
  const formData = new FormData()
  formData.append('image', file)
  const { data } = await http.post<import('../types/api').WarehouseProduct>(`/warehouse/products/${id}/image`, formData)
  return data
}

export async function fetchWarehouseStocks() {
  const { data } = await http.get<import('../types/api').WarehouseStock[]>('/warehouse/stocks')
  return data
}

export async function fetchWarehouseInboundOrders() {
  const { data } = await http.get<import('../types/api').WarehouseInboundOrder[]>('/warehouse/inbound-orders')
  return data
}

export async function createWarehouseInboundOrder(payload: import('../types/api').WarehouseInboundOrderPayload) {
  const { data } = await http.post<import('../types/api').WarehouseInboundOrder>('/warehouse/inbound-orders', payload)
  return data
}

export async function updateWarehouseInboundOrder(id: number, payload: import('../types/api').WarehouseInboundOrderPayload) {
  const { data } = await http.put<import('../types/api').WarehouseInboundOrder>(`/warehouse/inbound-orders/${id}`, payload)
  return data
}

export async function cancelWarehouseInboundOrder(id: number) {
  const { data } = await http.delete<import('../types/api').WarehouseInboundOrder>(`/warehouse/inbound-orders/${id}`)
  return data
}

export async function fetchWarehouseOutboundOrders() {
  const { data } = await http.get<import('../types/api').WarehouseOutboundOrder[]>('/warehouse/outbound-orders')
  return data
}

export async function createWarehouseOutboundOrder(payload: import('../types/api').WarehouseOutboundOrderPayload) {
  const { data } = await http.post<import('../types/api').WarehouseOutboundOrder>('/warehouse/outbound-orders', payload)
  return data
}

export async function updateWarehouseOutboundStatus(
  id: number,
  payload: { status: import('../types/api').WarehouseOutboundStatus; carrier?: string | null; tracking_no?: string | null },
) {
  const { data } = await http.patch<import('../types/api').WarehouseOutboundOrder>(`/warehouse/outbound-orders/${id}/status`, payload)
  return data
}

export async function fetchWarehouseMovements() {
  const { data } = await http.get<import('../types/api').WarehouseStockMovement[]>('/warehouse/movements')
  return data
}


export async function fetchSycmLatest(period: import('../types/api').SycmPeriod = 'today') {
  const { data } = await http.get<import('../types/api').SycmShopSnapshot[]>('/api/sycm/latest', {
    params: { period },
  })
  return data
}

export async function fetchSycmShopSnapshots(shopId: string, limit = 100) {
  const { data } = await http.get<import('../types/api').SycmShopSnapshot[]>(
    `/api/sycm/shops/${encodeURIComponent(shopId)}/snapshots`,
    { params: { limit } },
  )
  return data
}

export async function fetchSycmLatestSyncRequest() {
  const { data } = await http.get<import('../types/api').SycmSyncRequest | null>('/api/sycm/sync-requests/latest')
  return data
}

export async function createSycmSyncRequest() {
  const { data } = await http.post<import('../types/api').SycmSyncRequest>('/api/sycm/sync-requests')
  return data
}

export async function fetchSycmCollectorDevices() {
  const { data } = await http.get<import('../types/api').SycmCollectorDevice[]>('/api/sycm/collector-devices')
  return data
}
