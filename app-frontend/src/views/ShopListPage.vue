<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  IonContent,
  IonIcon,
  IonItem,
  IonItemOption,
  IonItemOptions,
  IonItemSliding,
  IonList,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSearchbar,
  alertController,
  toastController,
} from "@ionic/vue";
import {
  addOutline,
  chevronForwardOutline,
  createOutline,
  settingsOutline,
  trashOutline,
} from "ionicons/icons";
import { useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { api, ApiError } from "../api";
import { session } from "../session";
import {
  displayValue,
  loadShopData,
  searchableText,
  titleFor,
  type FieldDefinition,
  type ShopRecord,
} from "../shopRecords";

const router = useRouter();
const loading = ref(true);
const query = ref("");
const fields = ref<FieldDefinition[]>([]);
const records = ref<ShopRecord[]>([]);
const batchMode = ref(false);
const selected = ref<number[]>([]);
const canWrite = computed(() =>
  ["editor", "superadmin"].includes(session.user?.role || ""),
);
const canManageFields = computed(() => session.user?.role === "superadmin");
const previewFields = computed(() =>
  fields.value
    .filter(
      (field) =>
        !["shop_name", "store_name", "name"].includes(field.field_name),
    )
    .slice(0, 4),
);
const filtered = computed(() => {
  const keyword = query.value.trim().toLowerCase();
  return keyword
    ? records.value.filter((record) => searchableText(record).includes(keyword))
    : records.value;
});

const load = async (event?: { target: { complete: () => void } }) => {
  try {
    const data = await loadShopData();
    fields.value = data.fields;
    records.value = data.records;
  } catch (error) {
    const message =
      error instanceof ApiError ? error.detail : "店铺数据加载失败";
    const toast = await toastController.create({
      message,
      duration: 2200,
      color: "danger",
    });
    await toast.present();
  } finally {
    loading.value = false;
    event?.target.complete();
  }
};

const remove = async (record: ShopRecord) => {
  if (!canWrite.value) return;
  const alert = await alertController.create({
    header: "删除店铺记录",
    message: `确定删除“${titleFor(record, fields.value)}”吗？`,
    buttons: [
      "取消",
      {
        text: "删除",
        role: "destructive",
        handler: async () => {
          try {
            await api<void>(`/shop-records/${record.id}`, { method: "DELETE" });
            records.value = records.value.filter(
              (item) => item.id !== record.id,
            );
          } catch (error) {
            const toast = await toastController.create({
              message: error instanceof ApiError ? error.detail : "删除失败",
              duration: 2200,
              color: "danger",
            });
            await toast.present();
          }
        },
      },
    ],
  });
  await alert.present();
};

const toggle = (id: number) => {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((x) => x !== id)
    : [...selected.value, id];
};
const batchDelete = async () => {
  if (!selected.value.length) return;
  const alert = await alertController.create({
    header: "批量删除",
    message: `确定删除选中的 ${selected.value.length} 条店铺记录吗？`,
    buttons: [
      "取消",
      {
        text: "删除",
        role: "destructive",
        handler: async () => {
          try {
            await api("/shop-records/batch-delete", {
              method: "POST",
              body: JSON.stringify({ record_ids: selected.value }),
            });
            records.value = records.value.filter(
              (r) => !selected.value.includes(r.id),
            );
            selected.value = [];
            batchMode.value = false;
          } catch (error) {
            const toast = await toastController.create({
              message:
                error instanceof ApiError ? error.detail : "批量删除失败",
              duration: 2200,
              color: "danger",
            });
            await toast.present();
          }
        },
      },
    ],
  });
  await alert.present();
};
onMounted(() => load());
</script>

<template>
  <IonPage
    ><PageHeader
      title="店铺账号"
      :subtitle="`${records.length} 条店铺记录`"
      back
    /><IonContent>
      <IonRefresher slot="fixed" @ion-refresh="load"
        ><IonRefresherContent pulling-text="下拉刷新"
      /></IonRefresher>
      <main class="page-pad shops-page">
        <div class="search-line">
          <IonSearchbar
            v-model="query"
            placeholder="搜索店铺、平台或任意字段"
            mode="ios"
          /><button v-if="canWrite" @click="router.push('/tabs/form/shops')">
            <IonIcon :icon="addOutline" />新增
          </button>
        </div>
    <div class="result-line manage-line">
          <span>{{
            query ? `找到 ${filtered.length} 条` : `全部 ${records.length} 条`
          }}</span
          ><button v-if="canManageFields" @click="router.push('/tabs/shops/fields')">
            <IonIcon :icon="settingsOutline" />字段管理</button
          ><button
            v-if="canWrite"
            @click="
              batchMode = !batchMode;
              selected = [];
            "
          >
            {{ batchMode ? "退出批量" : "批量管理" }}</button
          ><button
            v-if="batchMode && selected.length"
            class="danger"
            @click="batchDelete"
          >
            删除 {{ selected.length }} 条
          </button>
        </div>
        <IonList v-if="filtered.length" class="shop-list" lines="none">
          <IonItemSliding v-for="record in filtered" :key="record.id">
            <IonItem
              class="shop-item"
              button
              :detail="false"
              @click="
                batchMode
                  ? toggle(record.id)
                  : router.push(`/tabs/detail/shops/${record.id}`)
              "
            >
              <article class="shop-card">
                <header>
                  <div>
                    <small>店铺记录 #{{ record.id }}</small>
                    <h2>{{ titleFor(record, fields) }}</h2>
                  </div>
                  <span
                    v-if="batchMode"
                    class="check"
                    :class="{ on: selected.includes(record.id) }"
                    >{{ selected.includes(record.id) ? "✓" : "" }}</span
                  ><IonIcon v-else :icon="chevronForwardOutline" />
                </header>
                <div class="shop-fields">
                  <div v-for="field in previewFields" :key="field.id">
                    <span>{{ field.label }}</span
                    ><strong>{{
                      displayValue(record.values[field.field_name])
                    }}</strong>
                  </div>
                </div>
              </article>
            </IonItem>
        <IonItemOptions v-if="canWrite && !batchMode" side="end"
              ><IonItemOption
                color="primary"
                @click="router.push(`/tabs/form/shops/${record.id}`)"
                ><IonIcon
                  slot="icon-only"
                  :icon="createOutline" /></IonItemOption
              ><IonItemOption color="danger" @click="remove(record)"
                ><IonIcon
                  slot="icon-only"
                  :icon="trashOutline" /></IonItemOption
            ></IonItemOptions>
          </IonItemSliding>
        </IonList>
        <div v-else-if="!loading" class="empty-state">
          {{ query ? "没有符合搜索条件的店铺记录" : "暂时没有店铺记录" }}
        </div>
      </main>
    </IonContent></IonPage
  >
</template>

<style scoped>
.shops-page {
  padding-inline: 12px;
}
.search-line {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: center;
}
.search-line ion-searchbar {
  --background: var(--app-card);
  --box-shadow: none;
  --border-radius: 14px;
  padding: 0;
}
.search-line > button {
  height: 44px;
  padding: 0 14px;
  border: 0;
  border-radius: 13px;
  color: #fff;
  background: #2563eb;
  display: flex;
  align-items: center;
  gap: 4px;
}
.result-line {
  display: flex;
  justify-content: space-between;
  margin: 10px 4px;
  color: var(--app-muted);
  font-size: 12px;
}
.manage-line{justify-content:flex-start;gap:7px;flex-wrap:wrap}.manage-line span{margin-right:auto}.manage-line button{padding:6px 9px;border:1px solid var(--app-line);border-radius:8px;color:#2563eb;background:var(--app-card)}.manage-line .danger{color:#dc2626}.check{width:24px;height:24px;border:2px solid var(--app-line);border-radius:7px;display:grid;place-items:center}.check.on{color:#fff;border-color:#2563eb;background:#2563eb}
.shop-list {
  padding: 0;
  background: transparent;
  display: grid;
  gap: 10px;
}
.shop-item {
  --padding-start: 0;
  --inner-padding-end: 0;
  --background: transparent;
}
.shop-card {
  width: 100%;
  padding: 16px;
  border: 1px solid var(--app-line);
  border-radius: 18px;
  background: var(--app-card);
}
.shop-card header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.shop-card small,
.shop-fields span {
  color: var(--app-muted);
  font-size: 11px;
}
.shop-card h2 {
  margin: 4px 0 0;
  font-size: 17px;
}
.shop-card header ion-icon {
  color: var(--app-muted);
}
.shop-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin-top: 13px;
  border-top: 1px solid var(--app-line);
}
.shop-fields div {
  min-width: 0;
  padding: 11px 10px 0 0;
}
.shop-fields strong {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}
.shop-fields div:nth-child(even) {
  padding-left: 12px;
  border-left: 1px solid var(--app-line);
}
</style>
