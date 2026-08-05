<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { fetchSystemSettings, saveSystemSettings } from '../api'
import type { SystemSettings } from '../types/api'

const loading = ref(false)
const saving = ref(false)
const form = reactive<SystemSettings>({
  license_expiry_days: 30, stale_task_days: 3, login_failure_threshold: 3,
  session_duration_hours: 168, low_stock_alert_enabled: true,
  pending_outbound_alert_enabled: true, task_alert_enabled: true, security_alert_enabled: true,
})

async function load() {
  loading.value = true
  try { Object.assign(form, await fetchSystemSettings()) }
  catch { ElMessage.error('加载系统设置失败') }
  finally { loading.value = false }
}

async function save() {
  saving.value = true
  try { Object.assign(form, await saveSystemSettings({ ...form })); ElMessage.success('系统设置已保存') }
  catch { ElMessage.error('保存系统设置失败') }
  finally { saving.value = false }
}
onMounted(load)
</script>

<template>
  <div class="page-stack">
    <section v-loading="loading" class="page-block settings-page">
      <div class="settings-section">
        <div class="settings-section__intro"><h3>异常提醒</h3><p>控制异常中心收集哪些业务问题，以及判断异常的时间范围。</p></div>
        <div class="settings-list">
          <div class="setting-row"><div><strong>低库存提醒</strong><span>商品可用库存达到预警值时生成提醒</span></div><el-switch v-model="form.low_stock_alert_enabled" /></div>
          <div class="setting-row"><div><strong>待出库提醒</strong><span>未发货、未取消的出库单进入提醒中心</span></div><el-switch v-model="form.pending_outbound_alert_enabled" /></div>
          <div class="setting-row"><div><strong>超时任务提醒</strong><span>任务超过指定天数仍未签收或结算时提醒</span></div><el-switch v-model="form.task_alert_enabled" /></div>
          <div class="setting-row"><div><strong>异常登录提醒</strong><span>同一账号和 IP 连续登录失败时提醒</span></div><el-switch v-model="form.security_alert_enabled" /></div>
        </div>
      </div>

      <div class="settings-section">
        <div class="settings-section__intro"><h3>提醒阈值</h3><p>修改后立即影响异常中心和运营工作台统计。</p></div>
        <div class="settings-grid">
          <el-form-item label="执照提前提醒天数"><el-input-number v-model="form.license_expiry_days" :min="1" :max="365" /><small>执照到期前多少天开始提醒</small></el-form-item>
          <el-form-item label="任务超时天数"><el-input-number v-model="form.stale_task_days" :min="1" :max="90" /><small>超过该天数仍未完成则提醒</small></el-form-item>
          <el-form-item label="登录失败提醒次数"><el-input-number v-model="form.login_failure_threshold" :min="1" :max="20" /><small>达到次数后进入安全异常</small></el-form-item>
          <el-form-item label="登录会话有效时长"><el-input-number v-model="form.session_duration_hours" :min="1" :max="720" /><small>单位：小时，新登录会话开始生效</small></el-form-item>
        </div>
      </div>

      <div class="settings-footer"><el-button type="primary" :loading="saving" @click="save">保存设置</el-button></div>
    </section>
  </div>
</template>

<style scoped>
.settings-page { padding: 0; overflow: hidden; }
.settings-section { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 28px; padding: 24px; border-bottom: 1px solid var(--panel-border); }
.settings-section__intro h3 { margin: 0 0 7px; font-size: 16px; }
.settings-section__intro p, .setting-row span, .settings-grid small { margin: 0; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
.settings-list { display: grid; }
.setting-row { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 64px; border-bottom: 1px solid #edf0f4; }
.setting-row:last-child { border-bottom: 0; }
.setting-row > div { display: grid; gap: 4px; }
.settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 28px; }
.settings-grid :deep(.el-form-item__content) { display: grid; justify-items: start; gap: 6px; }
.settings-footer { display: flex; justify-content: flex-end; padding: 18px 24px; }
@media (max-width: 760px) { .settings-section { grid-template-columns: 1fr; gap: 14px; } .settings-grid { grid-template-columns: 1fr; } }
</style>
