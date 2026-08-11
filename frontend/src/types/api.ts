export type RoleType = 'viewer' | 'editor' | 'superadmin'
export type PermissionLevel = 'none' | 'read' | 'write'
export type PermissionModule =
  | 'dashboard'
  | 'links'
  | 'task_bookkeeping'
  | 'dingtalk_profits'
  | 'shop_records'
  | 'peer_shops'
  | 'licenses'
  | 'account_usage'
  | 'mobile_devices'
  | 'warehouse'
export type AdminPermissions = Record<PermissionModule, PermissionLevel>

export interface CurrentUser {
  id: number
  username: string
  display_name: string | null
  role: RoleType
  is_active: boolean
  avatar_url: string | null
  avatar_name: string | null
  permissions: AdminPermissions
  totp_enabled: boolean
}

export interface AdminSessionInfo {
  id: number
  ip_address: string
  user_agent: string
  device_name: string
  created_at: string
  expires_at: string
  is_current: boolean
}

export interface AdminUser {
  id: number
  username: string
  display_name: string | null
  role: RoleType
  is_active: boolean
  permissions: AdminPermissions
  created_at: string
}

export interface AuditLog {
  id: number
  actor_user_id: number | null
  actor_username: string | null
  action: string
  resource_type: string
  resource_id: number | null
  details: Record<string, unknown>
  created_at: string
}

export interface DashboardRecentShopRecord {
  id: number
  shop_name: string
  platform: string | null
  date: string | null
  daily_revenue: number | null
}

export interface DashboardRecentLicenseRecord {
  id: number
  subject_name: string
  credit_code: string
  legal_representative: string | null
  expiry_date: string | null
}

export interface DashboardStats {
  shop_record_count: number
  license_record_count: number
  custom_field_count: number
  admin_user_count: number
  active_admin_count: number
  revenue_total: number
  deposit_total: number
  expired_license_count: number
  expiring_license_count: number
  banned_account_count: number
  pending_task_count: number
  pending_settlement_count: number
  recent_shop_records: DashboardRecentShopRecord[]
  recent_license_records: DashboardRecentLicenseRecord[]
}

export type SystemAlertCategory = 'inventory' | 'outbound' | 'license' | 'task' | 'security' | 'data'
export type SystemAlertSeverity = 'critical' | 'warning' | 'info'

export interface SystemAlertItem {
  key: string
  category: SystemAlertCategory
  severity: SystemAlertSeverity
  title: string
  description: string
  route: string
  occurred_at: string | null
  acknowledged: boolean
  acknowledged_at: string | null
  acknowledged_by: string | null
}

export interface SystemAlertList {
  total: number
  open_count: number
  acknowledged_count: number
  critical_count: number
  items: SystemAlertItem[]
}

export interface SystemSettings {
  system_name: string
  system_subtitle: string
  system_logo: string
  license_expiry_days: number
  stale_task_days: number
  login_failure_threshold: number
  session_duration_hours: number
  low_stock_alert_enabled: boolean
  pending_outbound_alert_enabled: boolean
  task_alert_enabled: boolean
  security_alert_enabled: boolean
}

export type SystemBranding = Pick<SystemSettings, 'system_name' | 'system_subtitle' | 'system_logo'>

export interface ServerServiceStatus {
  name: string
  display_name: string
  active_state: string
  sub_state: string
  description: string
  is_active: boolean
}

export interface ServerDatabaseStatus {
  name: string
  source: string
  relative_path: string
  category: 'active' | 'backup'
  status: string
  error_message: string | null
  main_size_bytes: number
  sidecar_size_bytes: number
  size_bytes: number
  modified_at: string
}

export type ServerNodeState = 'online' | 'stale' | 'missing'

export interface ServerNodeStatus {
  node_id: string
  label: string
  is_local: boolean
  state: ServerNodeState
  reported_at: string | null
  age_seconds: number | null
  message: string | null
  // null when the node has never reported, so the UI can tell "no data" apart
  // from a machine genuinely reading zero.
  metrics: ServerStatusMetrics | null
}

export interface ServerStatusMetrics {
  generated_at: string
  health: 'healthy' | 'warning' | 'critical'
  hostname: string
  operating_system: string
  architecture: string
  cpu_count: number
  cpu_percent: number | null
  load_1m: number | null
  load_5m: number | null
  load_15m: number | null
  memory_total_bytes: number
  memory_used_bytes: number
  memory_available_bytes: number
  memory_percent: number
  disk_total_bytes: number
  disk_used_bytes: number
  disk_free_bytes: number
  disk_percent: number
  system_uptime_seconds: number | null
  process_uptime_seconds: number
  process_id: number
  database_engine: string
  database_connection_status: string
  database_latency_ms: number | null
  database_error: string | null
  database_count: number
  database_total_size_bytes: number
  active_database_total_size_bytes: number
  backup_database_total_size_bytes: number
  services: ServerServiceStatus[]
  databases: ServerDatabaseStatus[]
}

// The local machine's readings stay at the top level for existing callers;
// `nodes` lists the whole fleet, this machine included.
export interface ServerStatus extends ServerStatusMetrics {
  nodes: ServerNodeStatus[]
}

export interface DingTalkProfitRecord {
  id: number
  source_record_id: number
  report_date: string
  store_name: string
  profit: number
  reporter_name: string
  reporter_id: string | null
  batch_id: string | null
  source_message_id: string | null
  source_create_time: string | null
  source_update_time: string | null
  synced_at: string
  created_at: string
  updated_at: string
}

export interface DingTalkProfitSummary {
  total_records: number
  total_profit: number
  unique_store_count: number
  unique_reporter_count: number
  latest_report_date: string | null
  latest_sync_time: string | null
}

export interface DingTalkProfitMonthlySummary {
  month: string
  total_profit: number
  record_count: number
  store_count: number
  reporter_count: number
  latest_report_date: string | null
}

export interface GlobalSearchResultItem {
  id: number
  category: 'shop_record' | 'license_record' | 'account_usage_record' | 'task_bookkeeping_record'
  title: string
  subtitle: string | null
  detail: string | null
  route: string
}

export interface GlobalSearchResponse {
  query: string
  total: number
  shop_records: GlobalSearchResultItem[]
  license_records: GlobalSearchResultItem[]
  account_usage_records: GlobalSearchResultItem[]
  task_bookkeeping_records: GlobalSearchResultItem[]
}

export interface ShopRecord {
  id: number
  values: Record<string, unknown>
}

export interface ShopRecordPayload {
  values: Record<string, unknown>
}

export interface BatchDeletePayload {
  record_ids: number[]
}

export interface BatchActionResult {
  updated_count: number
}

export type TaskStatusType = 'pending' | 'completed'

export interface CustomField {
  id: number
  field_name: string
  label: string
  field_type: 'text' | 'number' | 'date'
  required: boolean
  sort_order: number
  is_visible: boolean
  is_builtin: boolean
}

export interface CustomFieldCreatePayload {
  label: string
  field_name: string | null
  field_type: 'text' | 'number' | 'date'
  required: boolean
}

export interface CustomFieldUpdatePayload {
  required?: boolean
  is_visible?: boolean
}

export interface CustomFieldReorderPayload {
  field_ids: number[]
}

export interface LicenseRecord {
  id: number
  subject_name: string
  credit_code: string
  legal_representative: string | null
  issue_date: string | null
  expiry_date: string | null
  remark: string | null
  created_at: string
  image_url: string | null
  image_name: string | null
  extra_fields: Record<string, string | number | null>
}

export interface LicenseRecordPayload {
  subject_name: string
  credit_code: string
  legal_representative: string | null
  issue_date: string | null
  expiry_date: string | null
  remark: string | null
  extra_fields: Record<string, string | number | null>
}

export interface PeerShop {
  id: number
  shop_name: string
  shop_url: string | null
  remark: string | null
  created_at: string
  image_url: string | null
  image_name: string | null
  extra_fields: Record<string, string | number | null>
}

export interface PeerShopPayload {
  shop_name: string
  shop_url: string | null
  remark: string | null
  extra_fields: Record<string, string | number | null>
}

export interface AccountUsageRecord {
  id: number
  account_name: string
  phone_number: string | null
  device_name: string | null
  usage_notes: string | null
  is_banned: boolean
  banned_reason: string | null
  has_password: boolean
  created_at: string
  extra_fields: Record<string, string | number | null>
}

export interface AccountUsageRecordPayload {
  account_name: string | null
  password: string | null
  phone_number: string | null
  device_name: string | null
  usage_notes: string | null
  is_banned: boolean
  banned_reason: string | null
  extra_fields: Record<string, string | number | null>
}

export interface AccountUsagePasswordRevealPayload {
  current_password: string
}

export interface AccountUsageAccountNameRevealResponse {
  account_name: string | null
}

export interface AccountUsagePasswordRevealResponse {
  password: string | null
}

export interface AccountUsageBatchStatusPayload {
  record_ids: number[]
  is_banned: boolean
}

export interface MobileDeviceRecord {
  id: number
  device_name: string
  primary_card: string | null
  secondary_card: string | null
  remark: string | null
  created_at: string
  extra_fields: Record<string, string | number | null>
}

export interface MobileDeviceRecordPayload {
  device_name: string
  primary_card: string | null
  secondary_card: string | null
  remark: string | null
  extra_fields: Record<string, string | number | null>
}

export interface TaskBookkeepingShop {
  id: number
  name: string
  created_at: string
}

export interface TaskBookkeepingShopPayload {
  name: string
}

export interface TaskBookkeepingOwner {
  id: number
  name: string
  created_at: string
}

export interface TaskBookkeepingOwnerPayload {
  name: string
}

export interface TaskBookkeepingRecord {
  id: number
  order_no: string
  task_time: string
  shop_name: string
  owner_name: string
  principal_amount: number
  order_count: number
  commission_amount: number
  gift_amount: number
  signed_status: TaskStatusType
  settlement_status: TaskStatusType
  note: string | null
  created_at: string
  updated_at: string
}

export interface TaskBookkeepingRecordPayload {
  task_time: string | null
  shop_name: string
  owner_name: string
  principal_amount: number
  order_count: number
  commission_amount: number
  gift_amount: number
  signed_status: TaskStatusType
  settlement_status: TaskStatusType
  note: string | null
}

export interface TaskBookkeepingBatchStatusPayload {
  record_ids: number[]
  field: 'signed_status' | 'settlement_status'
  value: TaskStatusType
}

export interface TaskBookkeepingBatchDeletePayload {
  record_ids: number[]
}

export interface TaskBookkeepingBatchActionResult {
  updated_count: number
}

export interface SavedLink {
  id: number
  title: string
  url: string | null
  category: string | null
  description: string | null
  sort_order: number
  is_pinned: boolean
  images: Array<{
    name: string | null
    url: string
    storage_name: string
  }>
  image_url: string | null
  image_name: string | null
  author_user_id: number
  author_username: string
  author_avatar_url: string | null
  push_status: 'idle' | 'scheduled' | 'sending' | 'sent' | 'failed'
  push_scheduled_at: string | null
  push_sent_at: string | null
  push_error: string | null
  created_at: string
  updated_at: string
}

export interface SavedLinkPayload {
  title: string
  url: string | null
  category: string | null
  description: string | null
  sort_order: number
  is_pinned?: boolean
}

export interface SavedLinkPushPayload {
  scheduled_at: string | null
}

export interface TaskBookkeepingSummary {
  total_records: number
  unsettled_principal_total: number
  commission_total: number
  gift_total: number
  principal_total: number
  pending_signed_count: number
  pending_settlement_count: number
  recent_records: TaskBookkeepingRecord[]
}

export interface LoginPayload {
  username: string
  password: string
  captcha_id?: string | null
  captcha_code?: string | null
  totp_code?: string | null
}

export interface LoginCaptcha {
  captcha_id: string
  image_data: string
  expires_in_seconds: number
}

export interface TotpSetupResponse {
  secret: string
  provisioning_uri: string
  qr_image_data: string
}

export interface ChangePasswordPayload {
  current_password: string
  new_password: string
}

export interface CurrentUserProfilePayload {
  username: string
  display_name: string | null
}

export interface AdminUserCreatePayload {
  username: string
  password: string
  role: RoleType
  permissions?: Partial<AdminPermissions> | null
}

export interface AdminUserAccessPayload {
  role: RoleType
  permissions: AdminPermissions
}

export interface AdminUserPasswordResetPayload {
  new_password: string
}

export interface AdminUserStatusPayload {
  is_active: boolean
}

export interface SoftwareAdminUser {
  id: number
  username: string
  display_name: string | null
  role: 'software'
  is_active: boolean
  is_activated: boolean
  license_key: string | null
  plan_name: string | null
  license_status: string | null
  activated_at: string | null
  expire_at: string | null
  last_validated_at: string | null
  created_at: string
}

export interface Warehouse {
  id: number
  code: string
  name: string
  address: string | null
  contact_name: string | null
  contact_phone: string | null
  is_active: boolean
  remark: string | null
  created_at: string
  updated_at: string
}

export type WarehousePayload = Omit<Warehouse, 'id' | 'created_at' | 'updated_at'>

export interface WarehouseProduct {
  id: number
  sku: string
  name: string
  barcode: string | null
  specification: string | null
  unit: string
  cost_price: number
  warning_quantity: number
  is_active: boolean
  remark: string | null
  image_url: string | null
  image_name: string | null
  created_at: string
  updated_at: string
}

export type WarehouseProductPayload = Omit<WarehouseProduct, 'id' | 'created_at' | 'updated_at' | 'image_url' | 'image_name'>

export interface WarehouseStock {
  id: number | null
  warehouse_id: number
  warehouse_code: string
  warehouse_name: string
  product_id: number
  sku: string
  product_name: string
  barcode: string | null
  specification: string | null
  unit: string
  cost_price: number
  image_url: string | null
  quantity: number
  locked_quantity: number
  available_quantity: number
  warning_quantity: number
  is_low_stock: boolean
  updated_at: string | null
}

export interface WarehouseOrderLinePayload {
  product_id: number
  quantity: number
}

export interface WarehouseOrderLine extends WarehouseOrderLinePayload {
  sku: string
  product_name: string
  specification: string | null
  unit: string
  image_url: string | null
}

export interface WarehouseInboundOrder {
  id: number
  order_no: string
  warehouse_id: number
  warehouse_name: string
  source_type: 'purchase' | 'return' | 'other'
  supplier: string | null
  status: string
  remark: string | null
  operator_username: string | null
  completed_at: string | null
  created_at: string
  items: WarehouseOrderLine[]
}

export interface WarehouseInboundOrderPayload {
  warehouse_id: number
  source_type: 'purchase' | 'return' | 'other'
  supplier: string | null
  remark: string | null
  items: WarehouseOrderLinePayload[]
}

export type WarehouseOutboundStatus = 'pending' | 'picking' | 'checked' | 'packed' | 'shipped' | 'cancelled'

export interface WarehouseOutboundOrder {
  id: number
  order_no: string
  warehouse_id: number
  warehouse_name: string
  external_order_no: string | null
  delivery_method: 'shipping' | 'pickup'
  recipient_name: string | null
  recipient_phone: string | null
  recipient_address: string | null
  carrier: string | null
  tracking_no: string | null
  status: WarehouseOutboundStatus
  remark: string | null
  operator_username: string | null
  shipped_at: string | null
  created_at: string
  updated_at: string
  items: WarehouseOrderLine[]
}

export interface WarehouseOutboundOrderPayload {
  warehouse_id: number
  external_order_no: string | null
  delivery_method: 'shipping' | 'pickup'
  recipient_name: string | null
  recipient_phone: string | null
  recipient_address: string | null
  carrier: string | null
  tracking_no: string | null
  remark: string | null
  items: WarehouseOrderLinePayload[]
}

export interface WarehouseStockMovement {
  id: number
  warehouse_id: number
  warehouse_name: string
  product_id: number
  sku: string
  product_name: string
  movement_type: 'inbound' | 'outbound' | 'inbound_correction'
  quantity_change: number
  quantity_after: number
  reference_type: string
  reference_id: number
  reference_no: string
  operator_username: string | null
  remark: string | null
  created_at: string
}

export interface WarehouseSummary {
  warehouse_count: number
  product_count: number
  total_quantity: number
  total_cost: number
  low_stock_count: number
  pending_outbound_count: number
  today_inbound_quantity: number
  today_outbound_quantity: number
}

export type SycmPeriod = 'today' | 'yesterday' | 'recent7' | 'recent30'

export interface SycmOverviewMetric {
  value: number | null
  cycleCrc?: number | null
}

export interface SycmShopSnapshot {
  id?: number
  shopId: string
  shopName: string
  collectedAt: string
  receivedAt?: string
  period?: string
  uv: number | null
  pv: number | null
  cartByrCnt: number | null
  payByrCnt: number | null
  payAmt: number | null
  payRate: number | null
  overview?: Record<string, SycmOverviewMetric>
  sourceTree?: unknown[]
}

export interface SycmSourceNode {
  pageName?: SycmOverviewMetric | { value?: string | null }
  uv?: SycmOverviewMetric
  payByrCnt?: SycmOverviewMetric
  payAmt?: SycmOverviewMetric
}

export interface SycmSyncResult {
  shopId?: string
  shopName?: string
  success?: boolean
  error?: string | null
}

export interface SycmSyncRequest {
  id: number
  status: 'pending' | 'running' | 'completed' | 'failed' | string
  requestedAt: string | null
  claimedAt: string | null
  completedAt: string | null
  error: string | null
  results: SycmSyncResult[]
}

export type SycmSessionState = 'ready' | 'blocked' | 'unknown'

export interface SycmCollectorDevice {
  deviceId: string
  deviceName: string | null
  firstSeenAt: string | null
  lastSeenAt: string | null
  shopCount: number
  // Reachability only: the agent talked to the backend within the last minute.
  online: boolean
  // Whether that agent can actually read Qianniu. A running Qianniu locks every
  // cookie DB, so a reachable agent can still be unable to collect anything.
  sessionState: SycmSessionState
  sessionDetail: string
  sessionReportedAt: string | null
  // online && sessionState === 'ready', decided by the backend so both
  // frontends cannot disagree about it.
  collectable: boolean
}
