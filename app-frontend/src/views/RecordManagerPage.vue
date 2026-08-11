<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import {
  IonButton,
  IonContent,
  IonIcon,
  IonPage,
  IonSearchbar,
  IonSpinner,
  alertController,
  toastController,
} from "@ionic/vue";
import {
  copyOutline,
  createOutline,
  downloadOutline,
  expandOutline,
  trashOutline,
} from "ionicons/icons";
import { useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { api, ApiError } from "../api";
import { copyText } from "../clipboard";
import { apiUrl } from "../runtime";
import { session } from "../session";

type Row = Record<string, any>;
type Field = { key: string; label: string; required?: boolean; type?: string };
type Config = {
  title: string;
  endpoint: string;
  titleKey: string;
  fields: Field[];
  image?: boolean;
  status?: boolean;
};
const props = defineProps<{ detailId?: number }>();
const configs: Record<string, Config> = {
  peers: {
    title: "同行店铺",
    endpoint: "/peer-shops",
    titleKey: "shop_name",
    image: true,
    fields: [
      { key: "shop_name", label: "店铺名称", required: true },
      { key: "shop_url", label: "店铺链接", type: "url" },
      { key: "remark", label: "备注" },
    ],
  },
  licenses: {
    title: "执照档案",
    endpoint: "/license-records",
    titleKey: "subject_name",
    image: true,
    fields: [
      { key: "subject_name", label: "主体名称", required: true },
      { key: "credit_code", label: "统一信用代码", required: true },
      { key: "legal_representative", label: "法人代表" },
      { key: "issue_date", label: "签发日期", type: "date" },
      { key: "expiry_date", label: "到期日期", type: "date" },
      { key: "remark", label: "备注" },
    ],
  },
  "account-usage": {
    title: "账号使用记录",
    endpoint: "/account-usage-records",
    titleKey: "account_name",
    status: true,
    fields: [
      { key: "account_name", label: "账号名称", required: true },
      { key: "password", label: "密码", type: "password" },
      { key: "phone_number", label: "手机号" },
      { key: "device_name", label: "手机设备" },
      { key: "usage_notes", label: "使用说明" },
      { key: "banned_reason", label: "封禁原因" },
    ],
  },
  devices: {
    title: "手机设备",
    endpoint: "/mobile-devices",
    titleKey: "device_name",
    fields: [
      { key: "device_name", label: "设备名称", required: true },
      { key: "primary_card", label: "主卡" },
      { key: "secondary_card", label: "副卡" },
      { key: "remark", label: "备注" },
    ],
  },
};
const route = useRoute(),
  router = useRouter(),
  resource = computed(() => String(route.params.resource)),
  config = computed(() => configs[resource.value] || configs.peers);
const rows = ref<Row[]>([]),
  query = ref(""),
  loading = ref(false),
  selected = ref<number[]>([]),
  batch = ref(false),
  detail = ref<Row | null>(null),
  previewImage = ref(""),
  editor = ref(false),
  editing = ref<Row | null>(null),
  form = ref<Row>({}),
  imageFile = ref<File | null>(null);
const canWrite = computed(() =>
  ["editor", "superadmin"].includes(session.user?.role || ""),
);
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  return q
    ? rows.value.filter((row) => JSON.stringify(row).toLowerCase().includes(q))
    : rows.value;
});
const visible = computed(() => filtered.value);
watch(resource, () => {
  if (resource.value) load();
});
async function toast(message: string, color = "success") {
  const item = await toastController.create({ message, color, duration: 1800 });
  await item.present();
}
async function load() {
  loading.value = true;
  try {
    const data = await api<Row[] | { items?: Row[] }>(config.value.endpoint);
    rows.value = Array.isArray(data) ? data : data.items || [];
    if (props.detailId) {
      detail.value =
        rows.value.find((row) => row.id === props.detailId) || null;
    }
  } catch (error) {
    await toast(
      error instanceof ApiError ? error.detail : "加载失败",
      "danger",
    );
  } finally {
    loading.value = false;
  }
}
function openDetail(row: Row) {
  router.push(`/tabs/manage/${resource.value}/${row.id}`);
}
function displayValue(value: unknown) {
  if (value === true) return "是";
  if (value === false) return "否";
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}
const detailFields = computed(() =>
  detail.value
    ? config.value.fields
        .filter((field) => field.key !== "password")
        .map((field) => ({
          label: field.label,
          value: displayValue(detail.value?.[field.key]),
        }))
    : [],
);
const detailExtras = computed(() =>
  Object.entries(detail.value?.extra_fields || {}).map(([label, value]) => ({
    label,
    value: displayValue(value),
  })),
);
async function copyField(label: string, value: string) {
  if (value === "—") return toast("该字段没有内容", "warning");
  const copied = await copyText(value);
  await toast(
    copied ? `已复制：${label}` : "复制失败",
    copied ? "success" : "danger",
  );
}
async function copyAll() {
  const fields = [...detailFields.value, ...detailExtras.value].filter(
    (field) => field.value !== "—",
  );
  const text = fields
    .map((field) => `${field.label}：${field.value}`)
    .join("\n");
  if (!text) return toast("没有可复制的资料", "warning");
  const copied = await copyText(text);
  await toast(
    copied ? "全部资料已复制" : "复制失败",
    copied ? "success" : "danger",
  );
}
async function open(row?: Row) {
  let source = row || null;
  if (
    row &&
    resource.value === "account-usage" &&
    session.user?.role === "superadmin"
  )
    try {
      source = await api<Row>(`/account-usage-records/${row.id}/edit-detail`);
    } catch {}
  editing.value = source;
  form.value = Object.fromEntries(
    config.value.fields.map((field) => [field.key, source?.[field.key] ?? ""]),
  );
  if (
    row &&
    resource.value === "account-usage" &&
    session.user?.role !== "superadmin"
  )
    form.value.account_name = "";
  form.value.extra_fields = { ...(source?.extra_fields || {}) };
  imageFile.value = null;
  editor.value = true;
}
function payload() {
  const value: { [key: string]: any } = {
    extra_fields: form.value.extra_fields || {},
  };
  for (const field of config.value.fields) {
    if (
      editing.value &&
      ["password", "account_name"].includes(field.key) &&
      !form.value[field.key]
    )
      continue;
    value[field.key] = form.value[field.key] || null;
  }
  if (config.value.status) value.is_banned = Boolean(editing.value?.is_banned);
  return value;
}
async function save() {
  for (const field of config.value.fields)
    if (field.required && !String(form.value[field.key] || "").trim())
      return toast(`请填写${field.label}`, "warning");
  try {
    const row = await api<Row>(
      editing.value
        ? `${config.value.endpoint}/${editing.value.id}`
        : config.value.endpoint,
      {
        method: editing.value ? "PUT" : "POST",
        body: JSON.stringify(payload()),
      },
    );
    if (imageFile.value && config.value.image) {
      const data = new FormData();
      data.append("image", imageFile.value);
      const response = await fetch(
        apiUrl(`${config.value.endpoint}/${row.id}/image`),
        { method: "POST", credentials: "include", body: data },
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new ApiError(response.status, body.detail || "图片上传失败");
      }
    }
    editor.value = false;
    detail.value = null;
    await load();
    await toast("记录已保存");
  } catch (error) {
    await toast(
      error instanceof ApiError ? error.detail : "保存失败",
      "danger",
    );
  }
}
async function remove(ids: number[]) {
  if (!ids.length) return;
  const dialog = await alertController.create({
    header: ids.length > 1 ? "批量删除" : "删除记录",
    message: `确定删除 ${ids.length} 条记录吗？删除后不可恢复。`,
    buttons: ["取消", { text: "删除", role: "destructive" }],
  });
  await dialog.present();
  if ((await dialog.onDidDismiss()).role !== "destructive") return;
  try {
    if (ids.length === 1)
      await api(`${config.value.endpoint}/${ids[0]}`, { method: "DELETE" });
    else
      await api(`${config.value.endpoint}/batch-delete`, {
        method: "POST",
        body: JSON.stringify({ record_ids: ids }),
      });
    selected.value = [];
    batch.value = false;
    detail.value = null;
    await load();
    await toast("已删除");
  } catch (error) {
    await toast(
      error instanceof ApiError ? error.detail : "删除失败",
      "danger",
    );
  }
}
function toggle(id: number) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((item) => item !== id)
    : [...selected.value, id];
}
async function setBanned(is_banned: boolean) {
  if (!selected.value.length) return;
  try {
    await api("/account-usage-records/batch-status", {
      method: "PATCH",
      body: JSON.stringify({ record_ids: selected.value, is_banned }),
    });
    selected.value = [];
    batch.value = false;
    await load();
    await toast(is_banned ? "已批量封禁" : "已批量恢复");
  } catch (error) {
    await toast(
      error instanceof ApiError ? error.detail : "更新失败",
      "danger",
    );
  }
}
async function reveal(row: Row) {
  const dialog = await alertController.create({
    header: "验证查看密码",
    inputs: [
      {
        name: "current_password",
        type: "password",
        placeholder: "输入当前登录密码",
      },
    ],
    buttons: ["取消", { text: "验证", role: "confirm" }],
  });
  await dialog.present();
  const result = await dialog.onDidDismiss();
  if (result.role !== "confirm") return;
  try {
    const data = await api<{ password?: string }>(
      `/account-usage-records/${row.id}/reveal-password`,
      { method: "POST", body: JSON.stringify(result.data.values) },
    );
    await alertController
      .create({
        header: row.account_name,
        message: data.password || "未设置密码",
        buttons: ["关闭"],
      })
      .then((item) => item.present());
  } catch (error) {
    await toast(
      error instanceof ApiError ? error.detail : "验证失败",
      "danger",
    );
  }
}
async function saveImage(row: Row) {
  if (!row.image_url) return;
  try {
    const response = await fetch(row.image_url, { credentials: "include" });
    if (!response.ok) throw new Error("图片下载失败");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = row.image_name || `${config.value.title}-${row.id}.jpg`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    await toast("图片已保存");
  } catch (error) {
    await toast(
      error instanceof Error ? error.message : "图片保存失败",
      "danger",
    );
  }
}
function imageChanged(event: Event) {
  imageFile.value = (event.target as HTMLInputElement).files?.[0] || null;
}
onMounted(load);
</script>
<template>
  <IonPage
    ><PageHeader
      v-if="!props.detailId"
      :title="config.title"
      :subtitle="`${rows.length} 条同步记录`"
      back
    /><IonContent v-if="!props.detailId"
      ><main class="manager">
        <div class="toolbar">
          <IonSearchbar
            v-model="query"
            placeholder="搜索任意字段"
            mode="ios"
          /><button
            v-if="canWrite"
            @click="
              batch = !batch;
              selected = [];
            "
          >
            {{ batch ? "退出" : "批量" }}</button
          ><button v-if="canWrite" class="primary" @click="open()">新增</button>
        </div>
        <section class="list">
          <article
            v-for="row in visible"
            :key="row.id"
            :class="{ picked: selected.includes(row.id) }"
            @click="batch ? toggle(row.id) : openDetail(row)"
          >
            <span v-if="batch" class="check">{{
              selected.includes(row.id) ? "✓" : ""
            }}</span
            ><img
              v-else-if="row.image_url"
              :src="`${row.image_url}${String(row.image_url).includes('?') ? '&' : '?'}thumb=1`"
              alt=""
            /><i v-else>{{
              String(row[config.titleKey] || "?").slice(0, 1)
            }}</i>
            <div>
              <b>{{ row[config.titleKey] }}</b
              ><small>{{
                config.fields
                  .slice(1, 4)
                  .map((field) => row[field.key])
                  .filter(Boolean)
                  .join(" · ") || "暂无补充信息"
              }}</small>
            </div>
            <em v-if="row.is_banned">已封禁</em
            ><strong v-if="!batch">查看 ›</strong>
          </article>
          <p v-if="!filtered.length && !loading">暂无匹配记录</p>
        </section>
      </main>
      <div v-if="batch && selected.length" class="batchbar">
        <span>已选 {{ selected.length }} 条</span
        ><button v-if="resource === 'account-usage'" @click="setBanned(true)">
          封禁</button
        ><button v-if="resource === 'account-usage'" @click="setBanned(false)">
          恢复</button
        ><button class="danger" @click="remove(selected)">删除</button>
      </div></IonContent
    >
    <PageHeader
      v-if="props.detailId"
      :title="detail?.[config.titleKey] || config.title"
      :subtitle="`${config.title}详情`"
      back
    />
    <IonContent v-if="props.detailId">
      <main class="record-detail-page page-pad">
        <div v-if="!detail" class="detail-route-loading">
          <IonSpinner name="crescent" />
        </div>
        <template v-else>
          <section v-if="detail.image_url" class="detail-media panel">
            <button
              class="detail-image"
              aria-label="查看大图"
              @click="previewImage = detail.image_url"
            >
              <img :src="detail.image_url" alt="资料图片" />
            </button>
            <div class="image-actions">
              <IonButton fill="clear" @click="previewImage = detail.image_url"
                ><IonIcon
                  slot="start"
                  :icon="expandOutline"
                />查看大图</IonButton
              ><IonButton fill="clear" @click="saveImage(detail)"
                ><IonIcon
                  slot="start"
                  :icon="downloadOutline"
                />保存图片</IonButton
              >
            </div>
          </section>
          <button class="detail-copy-all panel" @click="copyAll">
            <IonIcon :icon="copyOutline" />
            <span>复制全部资料</span>
          </button>
          <section class="detail-fields panel">
            <div
              v-for="field in [...detailFields, ...detailExtras]"
              :key="field.label"
              class="detail-field"
              @click="copyField(field.label, field.value)"
            >
              <span>{{ field.label }}</span
              ><strong>{{ field.value }}</strong
              ><IonIcon :icon="copyOutline" aria-hidden="true" />
            </div>
          </section>
          <div class="detail-actions">
            <IonButton
              v-if="resource === 'account-usage'"
              fill="outline"
              @click="reveal(detail)"
              >查看密码</IonButton
            ><IonButton v-if="canWrite" @click="open(detail)"
              ><IonIcon slot="start" :icon="createOutline" />编辑资料</IonButton
            ><IonButton
              v-if="canWrite"
              color="danger"
              fill="outline"
              @click="remove([detail.id])"
              ><IonIcon slot="start" :icon="trashOutline" />删除</IonButton
            >
          </div>
        </template>
      </main>
    </IonContent>
    <div v-if="previewImage" class="image-preview" @click="previewImage = ''">
      <button aria-label="关闭大图" @click="previewImage = ''">关闭</button
      ><img :src="previewImage" alt="资料大图" @click.stop />
    </div>
    <div v-if="editor" class="mask" @click.self="editor = false">
      <section class="editor">
        <header>
          <b>{{ editing ? "编辑" : "新增" }}{{ config.title }}</b
          ><button @click="editor = false">关闭</button>
        </header>
        <label v-for="field in config.fields" :key="field.key"
          >{{ field.label
          }}<input
            v-model="form[field.key]"
            :type="field.type || 'text'"
            :required="field.required" /></label
        ><label
          >扩展字段 JSON<textarea
            :value="JSON.stringify(form.extra_fields || {}, null, 2)"
            rows="4"
            @change="
              (event) => {
                try {
                  form.extra_fields = JSON.parse(
                    (event.target as HTMLTextAreaElement).value,
                  );
                } catch {
                  toast('扩展字段必须是有效 JSON', 'warning');
                }
              }
            "
          ></textarea></label
        ><label v-if="config.image"
          >图片资料<input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="imageChanged" /></label
        ><button class="save" @click="save">保存</button>
      </section>
    </div></IonPage
  >
</template>
<style scoped>
.manager {
  padding: 10px 12px 90px;
}
.toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 7px;
  align-items: center;
}
.toolbar ion-searchbar {
  padding: 0;
  --box-shadow: none;
  --background: var(--app-card);
}
button {
  border: 1px solid var(--app-line);
  border-radius: 8px;
  padding: 9px;
  color: var(--app-text);
  background: var(--app-card);
}
button.primary,
.save {
  color: #fff;
  background: #1677ff;
}
.list {
  overflow: hidden;
  margin-top: 10px;
  border: 1px solid var(--app-line);
  border-radius: 10px;
  background: var(--app-card);
}
article {
  min-height: 68px;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 10px;
  border-bottom: 1px solid var(--app-line);
}
article.picked {
  background: #eff6ff;
}
article img,
article i,
.check {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  object-fit: cover;
  border-radius: 8px;
  color: #1677ff;
  background: #eaf2ff;
  font-style: normal;
}
article > div {
  min-width: 0;
  display: grid;
  flex: 1;
  gap: 4px;
}
article small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--app-muted);
  font-size: 10px;
}
article em {
  color: #dc2626;
  font-size: 10px;
  font-style: normal;
}
article > strong {
  color: var(--app-muted);
  font-size: 11px;
}
.danger {
  color: #dc2626;
}
.load-more {
  display: block;
  width: 100%;
  margin-top: 10px;
  color: #1677ff;
  background: var(--app-card);
}
.batchbar {
  position: fixed;
  z-index: 20;
  left: 12px;
  right: 12px;
  bottom: 18px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px;
  border: 1px solid var(--app-line);
  border-radius: 12px;
  background: var(--app-card);
  box-shadow: 0 8px 28px #0002;
}
.batchbar span {
  margin-right: auto;
}
.mask {
  position: fixed;
  z-index: 1200;
  inset: 0;
  display: flex;
  align-items: flex-end;
  background: #0f172a66;
}
.editor,
.detail {
  width: 100%;
  max-height: 88vh;
  overflow: auto;
  padding: 15px 14px 25px;
  border-radius: 10px 10px 0 0;
  background: var(--app-card);
}
.editor header,
.detail header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}
.detail header div {
  min-width: 0;
}
.detail header small,
.detail header b {
  display: block;
}
.detail header small {
  margin-bottom: 4px;
  color: var(--app-muted);
  font-size: 11px;
}
.detail header b {
  font-size: 18px;
}
.detail-image {
  display: block;
  width: 100%;
  max-height: 280px;
  margin-bottom: 8px;
  padding: 0;
  overflow: hidden;
  background: var(--ion-background-color);
}
.detail-image img {
  display: block;
  width: 100%;
  max-height: 278px;
  object-fit: contain;
}
.image-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}
.image-actions button {
  color: #1677ff;
}
.copy-all {
  width: 100%;
  margin-bottom: 10px;
  color: #1677ff;
}
.detail dl {
  margin: 0;
  border-top: 1px solid var(--app-line);
}
.detail dl > template {
  display: contents;
}
.detail dt,
.detail dd {
  margin: 0;
  padding: 11px 2px;
  border-bottom: 1px solid var(--app-line);
}
.detail dt {
  float: left;
  clear: left;
  width: 38%;
  color: var(--app-muted);
  font-size: 11px;
}
.detail dd {
  min-height: 38px;
  padding-left: 40%;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  overflow-wrap: anywhere;
  text-align: right;
  font-size: 13px;
  cursor: pointer;
}
.detail dd span {
  min-width: 0;
}
.detail dd ion-icon {
  flex: none;
  color: #94a3b8;
  font-size: 16px;
}
.detail footer {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 16px;
}
.image-preview {
  position: fixed;
  z-index: 1400;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 54px 10px 16px;
  background: #05070bea;
}
.image-preview > button {
  position: absolute;
  top: 12px;
  right: 12px;
  color: #fff;
  border-color: #ffffff55;
  background: #111827;
}
.image-preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  touch-action: pinch-zoom;
}
.editor label {
  display: grid;
  gap: 5px;
  margin-bottom: 10px;
  color: var(--app-muted);
  font-size: 11px;
}
.editor input,
.editor textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--app-line);
  border-radius: 7px;
  color: var(--app-text);
  background: var(--ion-background-color);
}
.save {
  width: 100%;
  height: 44px;
  border: 0;
}
</style>
<style scoped>
.detail-mask {
  align-items: stretch;
  background: var(--ion-background-color);
}
.detail-route-loading {
  position: fixed;
  z-index: 1199;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--app-blue);
  background: var(--ion-background-color);
}
.detail-mask .detail {
  width: 100%;
  height: 100%;
  max-height: none;
  overflow: auto;
  padding: 0;
  border-radius: 0;
  background: var(--ion-background-color);
}
.detail-mask .detail > header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) 44px;
  align-items: center;
  min-height: 64px;
  margin: 0;
  padding: 8px 10px;
  border-bottom: 1px solid var(--app-line);
  background: var(--app-card);
}
.detail-mask .detail > header > div {
  min-width: 0;
  text-align: center;
}
.detail-mask .detail > header small,
.detail-mask .detail > header b {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-mask .detail > header small {
  margin: 0 0 2px;
  color: var(--app-muted);
  font-size: 11px;
}
.detail-mask .detail > header b {
  color: var(--app-text);
  font-size: 17px;
}
.detail-close,
.header-copy {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--app-text);
  font-size: 22px;
}
.header-copy {
  color: #1677ff;
}
.detail-mask .detail > main {
  width: min(100%, 720px);
  display: grid;
  gap: 12px;
  margin: 0 auto;
  padding: 12px 14px calc(28px + env(safe-area-inset-bottom));
}
.detail-media {
  padding: 10px;
}
.detail-mask .detail-image {
  width: 100%;
  display: block;
  margin: 0;
  padding: 0;
  overflow: hidden;
  border: 0;
  border-radius: 10px;
  background: var(--app-soft);
}
.detail-mask .detail-image img {
  width: 100%;
  max-height: 320px;
  display: block;
  object-fit: contain;
}
.detail-mask .image-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  margin: 8px 0 0;
  border-top: 1px solid var(--app-line);
}
.detail-mask .image-actions ion-button {
  height: 42px;
  margin: 0;
  --color: #1677ff;
}
.detail-fields {
  overflow: hidden;
}
.detail-field {
  display: grid;
  grid-template-columns: minmax(90px, 35%) minmax(0, 1fr) 18px;
  align-items: center;
  gap: 10px;
  min-height: 48px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--app-line);
  cursor: pointer;
}
.detail-field:last-child {
  border-bottom: 0;
}
.detail-field span {
  color: var(--app-muted);
  font-size: 13px;
}
.detail-field strong {
  color: var(--app-text);
  font-size: 14px;
  text-align: right;
  overflow-wrap: anywhere;
  user-select: text;
}
.detail-field ion-icon {
  color: #94a3b8;
  font-size: 15px;
}
.detail-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
  gap: 10px;
}
.detail-actions ion-button {
  height: 48px;
  margin: 0;
  --border-radius: 13px;
}
.mask .editor {
  padding: 16px 14px calc(24px + env(safe-area-inset-bottom));
  border-radius: 14px 14px 0 0;
}
.mask .editor header {
  min-height: 42px;
  align-items: center;
  margin-bottom: 12px;
}
.mask .editor header b {
  font-size: 17px;
}
.mask .editor input,
.mask .editor textarea {
  border-color: var(--app-line);
  border-radius: 10px;
  background: var(--app-soft);
  color: var(--app-text);
}
.mask .editor .save {
  min-height: 46px;
  border-radius: 13px;
}

.record-detail-page {
  display: grid;
  gap: 12px;
}

.record-detail-page .detail-route-loading {
  position: static;
  min-height: 60vh;
  display: grid;
  place-items: center;
  color: var(--app-blue);
  background: transparent;
}

.record-detail-page .detail-image {
  width: 100%;
  display: block;
  margin: 0;
  padding: 0;
  overflow: hidden;
  border: 0;
  border-radius: 10px;
  background: var(--app-soft);
}

.record-detail-page .detail-image img {
  width: 100%;
  max-height: 320px;
  display: block;
  object-fit: contain;
}

.record-detail-page .image-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  margin: 8px 0 0;
  border-top: 1px solid var(--app-line);
}

.record-detail-page .image-actions ion-button {
  height: 42px;
  margin: 0;
  --color: var(--app-blue);
}

.detail-copy-all {
  min-height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  color: var(--app-blue);
  font-size: 14px;
}

.detail-copy-all ion-icon {
  font-size: 17px;
}

.mask:not(.detail-mask) {
  animation: record-backdrop-in 280ms cubic-bezier(0.2, 0.75, 0.25, 1) both;
}

.mask .editor {
  animation: record-content-in 280ms cubic-bezier(0.2, 0.75, 0.25, 1) both;
}

.image-preview {
  animation: record-backdrop-in 280ms cubic-bezier(0.2, 0.75, 0.25, 1) both;
}

.image-preview img {
  animation: record-content-in 280ms cubic-bezier(0.2, 0.75, 0.25, 1) both;
}

@keyframes record-backdrop-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes record-content-in {
  from {
    opacity: 0;
    transform: translateY(7px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .detail-mask,
  .detail-mask .detail,
  .mask:not(.detail-mask),
  .mask .editor,
  .image-preview,
  .image-preview img {
    animation: none;
  }
}
</style>
