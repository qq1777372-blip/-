<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  IonContent,
  IonPage,
  IonSearchbar,
  alertController,
  toastController,
} from "@ionic/vue";
import PageHeader from "../components/PageHeader.vue";
import { api, ApiError } from "../api";
type Device = {
  device_id: string;
  device_name?: string;
  platform?: string;
  app_version?: string;
  bound_at?: string;
  last_seen_at?: string;
};
type Key = {
  license_key: string;
  plan_name: string;
  status: string;
  duration_days?: number;
  max_devices: number;
  note?: string;
  feature_flags?: Record<string, unknown>;
  activated_at?: string;
  expires_at?: string;
  devices: Device[];
};
const keys = ref<Key[]>([]),
  stats = ref<Record<string, number>>({}),
  query = ref(""),
  status = ref(""),
  loading = ref(true),
  creating = ref(false),
  opened = ref<Key | null>(null),
  saving = ref(false);
const form = reactive({
  plan_name: "标准版",
  count: 5,
  duration_days: 30,
  max_devices: 1,
  note: "",
  feature_flags_text: '{"pro": true}',
});
const filtered = computed(() =>
  keys.value.filter(
    (k) =>
      (!status.value || k.status === status.value) &&
      (!query.value ||
        JSON.stringify(k).toLowerCase().includes(query.value.toLowerCase())),
  ),
);
const label = (s: string) =>
  s === "active"
    ? "生效中"
    : s === "disabled"
      ? "已禁用"
      : s === "expired"
        ? "已过期"
        : "未激活";
const fail = async (e: unknown) => {
  const t = await toastController.create({
    message:
      e instanceof ApiError
        ? e.detail
        : e instanceof Error
          ? e.message
          : "操作失败",
    duration: 2300,
    color: "danger",
  });
  await t.present();
};
const load = async () => {
  loading.value = true;
  try {
    [stats.value, keys.value] = await Promise.all([
      api<Record<string, number>>("/license-admin/stats"),
      api<Key[]>("/license-admin/licenses"),
    ]);
  } catch (e) {
    fail(e);
  } finally {
    loading.value = false;
  }
};
const createKeys = async () => {
  let flags = {};
  try {
    flags = form.feature_flags_text.trim()
      ? JSON.parse(form.feature_flags_text)
      : {};
  } catch {
    return fail(new Error("功能标记必须是 JSON 对象"));
  }
  saving.value = true;
  try {
    await api("/license-admin/licenses", {
      method: "POST",
      body: JSON.stringify({ ...form, feature_flags: flags }),
    });
    creating.value = false;
    await load();
  } catch (e) {
    fail(e);
  } finally {
    saving.value = false;
  }
};
const toggle = async (k: Key) => {
  try {
    await api(
      `/license-admin/licenses/${encodeURIComponent(k.license_key)}/status`,
      {
        method: "POST",
        body: JSON.stringify({
          status: k.status === "disabled" ? "active" : "disabled",
        }),
      },
    );
    await load();
  } catch (e) {
    fail(e);
  }
};
const unbind = async (k: Key, device?: Device) => {
  const a = await alertController.create({
    header: "确认解绑",
    message: device
      ? `确定解绑设备“${device.device_name || device.device_id}”吗？`
      : `确定清空 ${k.license_key} 的全部设备绑定吗？`,
    buttons: [
      "取消",
      {
        text: "确认解绑",
        role: "destructive",
        handler: async () => {
          try {
            await api(
              `/license-admin/licenses/${encodeURIComponent(k.license_key)}/unbind`,
              {
                method: "POST",
                body: JSON.stringify(
                  device ? { device_id: device.device_id } : {},
                ),
              },
            );
            await load();
            opened.value =
              keys.value.find((x) => x.license_key === k.license_key) || null;
          } catch (e) {
            fail(e);
          }
        },
      },
    ],
  });
  await a.present();
};
const copy = async (v: string) => {
  try {
    await navigator.clipboard.writeText(v);
    const t = await toastController.create({
      message: "卡密已复制",
      duration: 1200,
      color: "success",
    });
    await t.present();
  } catch {
    fail(new Error("复制失败"));
  }
};
onMounted(load);
</script>
<template>
  <IonPage
    ><PageHeader
      title="卡密管理"
      subtitle="卡密生成、启停和设备解绑"
      back
    /><IonContent
      ><main>
        <section class="stats">
          <div>
            <span>卡密总数</span
            ><b>{{ stats.total_licenses || keys.length }}</b>
          </div>
          <div>
            <span>生效中</span><b>{{ stats.active_licenses || 0 }}</b>
          </div>
          <div>
            <span>已禁用</span><b>{{ stats.disabled_licenses || 0 }}</b>
          </div>
          <div>
            <span>绑定设备</span><b>{{ stats.bound_devices || 0 }}</b>
          </div>
        </section>
        <div class="toolbar">
          <IonSearchbar
            v-model="query"
            placeholder="搜索卡密、套餐或设备"
            mode="ios"
          /><button @click="creating = true">生成卡密</button>
        </div>
        <nav>
          <button :class="{ on: !status }" @click="status = ''">全部</button
          ><button
            :class="{ on: status === 'active' }"
            @click="status = 'active'"
          >
            生效中</button
          ><button
            :class="{ on: status === 'disabled' }"
            @click="status = 'disabled'"
          >
            已禁用</button
          ><button
            :class="{ on: status === 'expired' }"
            @click="status = 'expired'"
          >
            已过期
          </button>
        </nav>
        <section class="list">
          <article v-for="k in filtered" :key="k.license_key">
            <header>
              <div>
                <code>{{ k.license_key }}</code>
                <p>{{ k.plan_name }} · {{ label(k.status) }}</p>
              </div>
              <span>{{ k.devices?.length || 0 }}/{{ k.max_devices }} 台</span>
            </header>
            <div class="meta">
              <span>{{
                k.duration_days === 0 ? "永久" : `${k.duration_days || 0} 天`
              }}</span
              ><span
                >到期 {{ String(k.expires_at || "未激活").slice(0, 10) }}</span
              ><span>{{ k.note || "暂无备注" }}</span><span v-for="(flag,name) in k.feature_flags" :key="name">{{ name }}: {{ flag }}</span>
            </div>
            <footer>
              <button @click="copy(k.license_key)">复制</button
              ><button @click="opened = k">绑定设备</button
              ><button @click="toggle(k)">
                {{ k.status === "disabled" ? "启用" : "禁用" }}</button
              ><button
                v-if="k.devices?.length"
                class="danger"
                @click="unbind(k)"
              >
                解绑全部
              </button>
            </footer>
          </article>
          <div v-if="!filtered.length && !loading" class="empty-state">
            没有匹配的卡密
          </div>
        </section>
      </main>
      <div v-if="creating" class="sheet">
        <section>
          <h2>生成卡密</h2>
          <label>套餐名称<input v-model="form.plan_name" /></label>
          <div class="grid">
            <label
              >生成数量<input
                v-model.number="form.count"
                type="number"
                min="1"
                max="100" /></label
            ><label
              >有效天数<input
                v-model.number="form.duration_days"
                type="number"
                min="0"
              /><small>0 表示永久</small></label
            ><label
              >最大设备数<input
                v-model.number="form.max_devices"
                type="number"
                min="1"
            /></label>
          </div>
          <label>备注<input v-model="form.note" /></label
          ><label
            >功能标记（JSON）<textarea
              v-model="form.feature_flags_text"
              rows="3"
            ></textarea>
          </label>
          <footer>
            <button @click="creating = false">取消</button
            ><button class="primary" :disabled="saving" @click="createKeys">
              确认生成
            </button>
          </footer>
        </section>
      </div>
      <div v-if="opened" class="sheet">
        <section>
          <h2>设备绑定</h2>
          <p class="key">{{ opened.license_key }}</p>
          <div class="devices">
            <article v-for="d in opened.devices" :key="d.device_id">
              <div>
                <b>{{ d.device_name || "未命名设备" }}</b
                ><small
                  >{{ d.device_id }} · {{ d.platform || "未知平台" }} ·
                  {{ d.app_version || "未知版本" }}</small
                ><small
                  >最近心跳
                  {{
                    String(d.last_seen_at || "—")
                      .replace("T", " ")
                      .slice(0, 16)
                  }}</small
                >
              </div>
              <button class="danger" @click="unbind(opened, d)">解绑</button>
            </article>
            <div v-if="!opened.devices?.length" class="empty-state">
              当前没有绑定设备
            </div>
          </div>
          <footer>
            <button @click="opened = null">关闭</button
            ><button
              v-if="opened.devices?.length"
              class="danger"
              @click="unbind(opened)"
            >
              解绑全部
            </button>
          </footer>
        </section>
      </div></IonContent
    ></IonPage
  >
</template>
<style scoped>
main {
  padding: 12px;
}
.stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
}
.stats div {
  padding: 12px;
  border: 1px solid var(--app-line);
  background: var(--app-card);
}
.stats span,
.stats b {
  display: block;
}
.stats span {
  color: var(--app-muted);
  font-size: 11px;
}
.stats b {
  margin-top: 4px;
  font-size: 21px;
}
.toolbar {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  margin: 12px 0;
}
.toolbar ion-searchbar {
  --background: var(--app-card);
  --box-shadow: none;
  padding: 0;
}
.toolbar button,
.primary {
  border: 0;
  color: #fff;
  background: #2563eb;
}
nav {
  display: flex;
  gap: 6px;
  overflow: auto;
  margin-bottom: 10px;
}
button {
  padding: 8px 10px;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  color: var(--app-text);
  background: var(--app-card);
}
nav button {
  flex: none;
}
nav .on {
  color: #2563eb;
  border-color: #8fb3ff;
}
.list {
  display: grid;
  gap: 9px;
}
.list > article {
  padding: 14px;
  border: 1px solid var(--app-line);
  background: var(--app-card);
}
header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
code {
  font-size: 13px;
  overflow-wrap: anywhere;
}
p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 11px;
}
header > span {
  white-space: nowrap;
  color: #2563eb;
  font-size: 12px;
}
.meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.meta span {
  padding: 4px 7px;
  background: var(--app-soft);
  font-size: 10px;
}
.list footer {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 11px;
}
.danger {
  color: #dc2626;
}
.sheet {
  position: fixed;
  z-index: 50;
  inset: 0;
  display: flex;
  align-items: flex-end;
  background: #0007;
}
.sheet > section {
  box-sizing: border-box;
  width: 100%;
  max-height: 90%;
  overflow: auto;
  padding: 18px 14px calc(18px + env(safe-area-inset-bottom));
  background: var(--app-card);
}
.sheet h2 {
  margin: 0 0 14px;
}
.sheet label {
  display: block;
  margin: 11px 0;
  color: var(--app-muted);
  font-size: 12px;
}
.sheet input,
.sheet textarea {
  box-sizing: border-box;
  width: 100%;
  margin-top: 6px;
  padding: 11px;
  border: 1px solid var(--app-line);
  color: var(--app-text);
  background: var(--ion-background-color);
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.sheet footer {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 8px;
  margin-top: 15px;
}
.devices {
  border: 1px solid var(--app-line);
}
.devices article {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid var(--app-line);
}
.devices small {
  display: block;
  margin-top: 4px;
  color: var(--app-muted);
  font-size: 10px;
  overflow-wrap: anywhere;
}
.key {
  margin-bottom: 12px;
  overflow-wrap: anywhere;
}
@media (max-width: 380px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
