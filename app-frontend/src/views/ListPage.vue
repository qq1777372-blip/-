<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSearchbar,
  alertController,
  onIonViewWillLeave,
  toastController,
} from "@ionic/vue";
import { useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { api, ApiError } from "../api";
type Row = Record<string, any>;
type Config = {
  title: string;
  endpoint: string;
  titleKeys: string[];
  subKeys: string[];
  imageKey?: string;
};
// imageKey is only set for the two resources whose backend rows carry an
// image_path (licenses, peers). The other eight share this page and must keep
// rendering the first title character as their icon.
const configs: Record<string, Config> = {
  links: {
    title: "链接广场",
    endpoint: "/saved-links",
    titleKeys: ["title"],
    subKeys: ["category", "description", "url"],
  },
  peers: {
    title: "同行店铺",
    endpoint: "/peer-shops",
    titleKeys: ["shop_name"],
    subKeys: ["shop_url", "remark"],
    imageKey: "image_url",
  },
  licenses: {
    title: "执照档案",
    endpoint: "/license-records",
    titleKeys: ["subject_name"],
    subKeys: ["credit_code", "legal_representative", "expiry_date"],
    imageKey: "image_url",
  },
  devices: {
    title: "手机设备",
    endpoint: "/mobile-devices",
    titleKeys: ["device_name"],
    subKeys: ["primary_card", "secondary_card", "remark"],
  },
  users: {
    title: "账号与权限",
    endpoint: "/admin-users",
    titleKeys: ["display_name", "username"],
    subKeys: ["username", "role", "account_type"],
  },
  "license-keys": {
    title: "卡密管理",
    endpoint: "/license-admin/licenses",
    titleKeys: ["license_key", "key"],
    subKeys: ["plan_name", "status", "expire_at", "expires_at"],
  },
  "software-users": {
    title: "软件账号",
    endpoint: "/software-admin/users",
    titleKeys: ["display_name", "username"],
    subKeys: ["username", "license_key", "license_status", "expire_at"],
  },
  owners: {
    title: "负责人管理",
    endpoint: "/task-bookkeeping/owners",
    titleKeys: ["name"],
    subKeys: ["remark", "created_at"],
  },
  "account-usage": {
    title: "账号使用记录",
    endpoint: "/account-usage-records",
    titleKeys: ["account_name"],
    subKeys: ["phone_number", "device_name", "usage_notes"],
  },
  "audit-logs": {
    title: "安全日志",
    endpoint: "/audit-logs",
    titleKeys: ["action"],
    subKeys: ["actor_username", "resource_type", "created_at"],
  },
};
const route = useRoute();
const router = useRouter();
const resource = computed(() => String(route.params.resource));
const config = computed(
  () =>
    configs[resource.value] || {
      title: "数据列表",
      endpoint: `/${resource.value}`,
      titleKeys: ["name", "title"],
      subKeys: ["remark", "created_at"],
    },
);
const rows = ref<Row[]>([]);
const query = ref(""),
  facet = ref(""),
  sortDesc = ref(true),
  page = ref(1),
  pageSize = ref(20);
const loading = ref(true);
const loadError = ref("");
let activeToast: HTMLIonToastElement | null = null;
const manageable = computed(() =>
  ["owners", "users", "license-keys"].includes(resource.value),
);
const value = (row: Row, keys: string[]) =>
  keys
    .map((key) => row[key])
    .find((item) => item !== undefined && item !== null && item !== "") || "—";
const facetKey = computed(() =>
  resource.value === "software-users"
    ? "status"
    : resource.value === "audit-logs"
      ? "action"
      : "",
);
const facets = computed(() => [
  ...new Set(rows.value.map((row) => row[facetKey.value]).filter(Boolean)),
]);
const filtered = computed(() =>
  rows.value
    .filter(
      (row) =>
        (!query.value ||
          JSON.stringify(row)
            .toLowerCase()
            .includes(query.value.toLowerCase())) &&
        (!facet.value || row[facetKey.value] === facet.value),
    )
    .sort(
      (a, b) =>
        (Number(a.id || 0) - Number(b.id || 0)) * (sortDesc.value ? -1 : 1),
    ),
);
const visible = computed(() =>
  filtered.value.slice(
    (page.value - 1) * pageSize.value,
    page.value * pageSize.value,
  ),
);
const rowKey = (row: Row, index: number) =>
  String(row.id ?? row.license_key ?? row.key ?? row.username ?? index);
const dismissToast = async () => {
  const toast = activeToast;
  activeToast = null;
  if (toast) await toast.dismiss().catch(() => undefined);
};
const error = async (e: unknown) => {
  await dismissToast();
  const t = await toastController.create({
    message: e instanceof ApiError ? e.detail : "操作失败",
    duration: 2200,
    color: "danger",
  });
  activeToast = t;
  t.addEventListener(
    "ionToastDidDismiss",
    () => {
      if (activeToast === t) activeToast = null;
    },
    { once: true },
  );
  await t.present();
};
const load = async (event?: { target: { complete: () => void } }) => {
  loading.value = true;
  loadError.value = "";
  try {
    const data = await api<Row[] | { items?: Row[] }>(config.value.endpoint);
    rows.value = Array.isArray(data) ? data : data.items || [];
  } catch (e) {
    rows.value = [];
    loadError.value =
      e instanceof ApiError && e.status === 404
        ? "当前服务器暂未提供此功能，请联系管理员更新后端服务。"
        : e instanceof ApiError
          ? e.detail
          : "数据加载失败，请检查网络后重试。";
  } finally {
    loading.value = false;
    event?.target.complete();
  }
};
const add = async () => {
  if (resource.value === "owners") {
    const a = await alertController.create({
      header: "新增负责人",
      inputs: [{ name: "name", placeholder: "负责人姓名" }],
      buttons: ["取消", { text: "新增", role: "confirm" }],
    });
    await a.present();
    const r = await a.onDidDismiss();
    if (r.role === "confirm")
      try {
        await api("/task-bookkeeping/owners", {
          method: "POST",
          body: JSON.stringify({ name: r.data.values.name }),
        });
        await load();
      } catch (e) {
        error(e);
      }
  } else if (resource.value === "users") {
    const a = await alertController.create({
      header: "新增管理账号",
      inputs: [
        { name: "username", placeholder: "登录账号" },
        { name: "password", type: "password", placeholder: "初始密码" },
        {
          name: "role",
          type: "radio",
          label: "超级管理员",
          value: "superadmin",
        },
        {
          name: "role",
          type: "radio",
          label: "编辑",
          value: "editor",
          checked: true,
        },
        { name: "role", type: "radio", label: "只读", value: "viewer" },
      ],
      buttons: ["取消", { text: "新增", role: "confirm" }],
    });
    await a.present();
    const r = await a.onDidDismiss();
    if (r.role === "confirm")
      try {
        await api("/admin-users", {
          method: "POST",
          body: JSON.stringify({ ...r.data.values, permissions: {} }),
        });
        await load();
      } catch (e) {
        error(e);
      }
  } else {
    const a = await alertController.create({
      header: "生成卡密",
      inputs: [
        { name: "plan_name", placeholder: "授权方案" },
        { name: "count", type: "number", placeholder: "数量", value: 1 },
        {
          name: "duration_days",
          type: "number",
          placeholder: "有效天数",
          value: 30,
        },
        {
          name: "max_devices",
          type: "number",
          placeholder: "设备数",
          value: 1,
        },
        { name: "note", placeholder: "备注" },
      ],
      buttons: ["取消", { text: "生成", role: "confirm" }],
    });
    await a.present();
    const r = await a.onDidDismiss();
    if (r.role === "confirm")
      try {
        await api("/license-admin/licenses", {
          method: "POST",
          body: JSON.stringify(r.data.values),
        });
        await load();
      } catch (e) {
        error(e);
      }
  }
};
const manage = async (row: Row) => {
  if (resource.value === "owners") {
    const a = await alertController.create({
      header: "删除负责人",
      message: `确定删除“${row.name}”吗？`,
      buttons: [
        "取消",
        {
          text: "删除",
          role: "destructive",
          handler: async () => {
            try {
              await api(`/task-bookkeeping/owners/${row.id}`, {
                method: "DELETE",
              });
              await load();
            } catch (e) {
              error(e);
            }
          },
        },
      ],
    });
    await a.present();
    return;
  }
  if (resource.value === "users") {
    const a = await alertController.create({
      header: row.username,
      buttons: [
        {
          text: row.is_active === false ? "启用账号" : "禁用账号",
          handler: async () => {
            try {
              await api(`/admin-users/${row.id}/status`, {
                method: "PATCH",
                body: JSON.stringify({ is_active: row.is_active === false }),
              });
              await load();
            } catch (e) {
              error(e);
            }
          },
        },
        { text: "重置密码", handler: () => resetPassword(row) },
        { text: "取消", role: "cancel" },
      ],
    });
    await a.present();
    return;
  }
  const key = row.license_key || row.key;
  const a = await alertController.create({
    header: "管理卡密",
    buttons: [
      {
        text: row.status === "disabled" ? "启用" : "禁用",
        handler: async () => {
          try {
            await api(
              `/license-admin/licenses/${encodeURIComponent(key)}/status`,
              {
                method: "POST",
                body: JSON.stringify({
                  status: row.status === "disabled" ? "active" : "disabled",
                }),
              },
            );
            await load();
          } catch (e) {
            error(e);
          }
        },
      },
      {
        text: "解绑全部设备",
        handler: async () => {
          try {
            await api(
              `/license-admin/licenses/${encodeURIComponent(key)}/unbind`,
              { method: "POST", body: "{}" },
            );
            await load();
          } catch (e) {
            error(e);
          }
        },
      },
      { text: "取消", role: "cancel" },
    ],
  });
  await a.present();
};
const resetPassword = async (row: Row) => {
  const a = await alertController.create({
    header: `重置 ${row.username} 的密码`,
    inputs: [{ name: "new_password", type: "password", placeholder: "新密码" }],
    buttons: ["取消", { text: "确认", role: "confirm" }],
  });
  await a.present();
  const r = await a.onDidDismiss();
  if (r.role === "confirm")
    try {
      await api(`/admin-users/${row.id}/password`, {
        method: "PATCH",
        body: JSON.stringify(r.data.values),
      });
      const t = await toastController.create({
        message: "密码已重置",
        duration: 1500,
        color: "success",
      });
      await t.present();
    } catch (e) {
      error(e);
    }
};
const openRow = (row: Row, index: number) =>
  manageable.value
    ? manage(row)
    : router.push(
        `/tabs/detail/${resource.value}/${encodeURIComponent(rowKey(row, index))}`,
      );
// Ask the backend for a downscaled copy: the originals run up to 12 MB each, and
// this list renders them at 38px. Full-size is still used by the fullscreen
// preview and by "save image".
const thumbUrl = (url: string) =>
  url ? `${url}${url.indexOf("?") >= 0 ? "&" : "?"}thumb=1` : url;
// A broken image would otherwise leave an empty box, so fall back to the same
// letter tile the other resources use.
const fallbackToLetter = (event: Event, row: Row) => {
  const img = event.target as HTMLImageElement | null;
  if (!img) return;
  const box = img.parentElement;
  if (!box) return;
  box.className = "row-icon";
  box.textContent = String(value(row, config.value.titleKeys)).slice(0, 1);
};
watch([query, facet, pageSize], () => { page.value = 1 });
watch(resource, () => { page.value = 1; facet.value = ''; load() });
onMounted(load);
onIonViewWillLeave(dismissToast);
onUnmounted(dismissToast);
</script>
<template>
  <IonPage
    ><PageHeader
      :title="config.title"
      :subtitle="`共 ${rows.length} 条记录`"
      back
    /><IonContent
      ><IonRefresher slot="fixed" @ion-refresh="load"
        ><IonRefresherContent
      /></IonRefresher>
      <main class="page-pad real-list">
        <div class="toolbar">
          <IonSearchbar
            v-model="query"
            placeholder="搜索任意字段"
            mode="ios"
          /><button v-if="manageable" @click="add">新增</button>
        </div>
        <div class="list-filters"><select v-if="facetKey" v-model="facet"><option value="">全部{{resource==='audit-logs'?'动作':'状态'}}</option><option v-for="item in facets" :key="item" :value="item">{{item}}</option></select><button @click="sortDesc=!sortDesc">{{sortDesc?'最新优先':'最早优先'}}</button></div>
        <div v-if="loadError" class="load-error">
          <strong>暂时无法加载</strong>
          <p>{{ loadError }}</p>
          <button @click="load()">重新加载</button>
        </div>
        <section v-else class="compact-list">
          <article
            v-for="(row, index) in visible"
            :key="rowKey(row, index)"
            class="compact-row real-row"
            @click="openRow(row, index)"
          >
            <span
              v-if="config.imageKey && row[config.imageKey]"
              class="row-icon row-icon--thumb"
              ><img
                :src="thumbUrl(row[config.imageKey])"
                alt=""
                loading="lazy"
                decoding="async"
                @error="fallbackToLetter($event, row)" /></span
            ><span v-else class="row-icon">{{
              String(value(row, config.titleKeys)).slice(0, 1)
            }}</span>
            <div>
              <h3>{{ value(row, config.titleKeys) }}</h3>
              <p>
                {{
                  config.subKeys
                    .map((key) => row[key])
                    .filter(Boolean)
                    .join(" · ") || "暂无补充信息"
                }}
              </p>
            </div>
            <strong>{{ manageable ? "管理" : "详情" }} ›</strong>
          </article>
        </section>
        <div
          v-if="!loadError && !filtered.length && !loading"
          class="empty-state"
        >
          暂无符合条件的数据
        </div>
        <div class="pager"><span>共 {{filtered.length}} 条</span><select v-model.number="pageSize"><option :value="20">20/页</option><option :value="50">50/页</option></select><button :disabled="page<=1" @click="page--">上一页</button><b>{{page}}/{{Math.max(1,Math.ceil(filtered.length/pageSize))}}</b><button :disabled="page>=Math.ceil(filtered.length/pageSize)" @click="page++">下一页</button></div>
      </main></IonContent
    ></IonPage
  >
</template>
<style scoped>
.toolbar {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}
.toolbar ion-searchbar {
  --background: var(--app-card);
  --box-shadow: none;
  --border-radius: 14px;
  padding: 0;
}
.toolbar button {
  height: 44px;
  padding: 0 15px;
  border: 0;
  border-radius: 12px;
  color: #fff;
  background: #2563eb;
}
.list-filters,.pager{display:flex;align-items:center;gap:7px;margin-bottom:10px}.list-filters select,.list-filters button,.pager select,.pager button{height:34px;padding:0 9px;border:1px solid var(--app-line);border-radius:8px;color:var(--app-text);background:var(--app-card)}.pager{margin-top:10px;font-size:10px}.pager span{margin-right:auto}.pager button:disabled{opacity:.35}
.load-error {
  padding: 32px 20px;
  text-align: center;
  color: var(--app-text);
}
.load-error strong {
  display: block;
  font-size: 16px;
}
.load-error p {
  margin: 8px auto 18px;
  max-width: 360px;
  color: var(--app-muted);
  font-size: 13px;
  line-height: 1.6;
}
.load-error button {
  height: 40px;
  padding: 0 18px;
  border: 0;
  border-radius: 8px;
  color: #fff;
  background: #2563eb;
}
.real-row strong {
  color: var(--app-muted);
  font-size: 11px;
}
.row-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: #2563eb;
  background: #eaf2ff;
  font-weight: 700;
}
.real-row p {
  max-width: 230px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-icon--thumb {
  overflow: hidden;
  padding: 0;
  background: var(--app-soft, #eaf2ff);
}
.row-icon--thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
