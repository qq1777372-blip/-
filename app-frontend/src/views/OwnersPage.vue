<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSearchbar,
  alertController,
  toastController,
} from "@ionic/vue";
import PageHeader from "../components/PageHeader.vue";
import { api, ApiError } from "../api";
type Owner = { id: number; name: string; created_at?: string };
type Task = { owner_name?: string };
const owners = ref<Owner[]>([]),
  tasks = ref<Task[]>([]),
  query = ref(""),
  loading = ref(true);
const counts = computed(() => {
  const map = new Map<string, number>();
  tasks.value.forEach(
    (t) =>
      t.owner_name && map.set(t.owner_name, (map.get(t.owner_name) || 0) + 1),
  );
  return map;
});
const filtered = computed(() =>
  owners.value.filter((o) =>
    o.name.toLowerCase().includes(query.value.trim().toLowerCase()),
  ),
);
const fail = async (e: unknown) => {
  const t = await toastController.create({
    message: e instanceof ApiError ? e.detail : "操作失败",
    duration: 2200,
    color: "danger",
  });
  await t.present();
};
const load = async (event?: { target: { complete: () => void } }) => {
  try {
    const [a, b] = await Promise.all([
      api<Owner[]>("/task-bookkeeping/owners"),
      api<Task[]>("/task-bookkeeping/records"),
    ]);
    owners.value = a;
    tasks.value = b;
  } catch (e) {
    fail(e);
  } finally {
    loading.value = false;
    event?.target.complete();
  }
};
const add = async () => {
  const a = await alertController.create({
    header: "新增负责人",
    inputs: [{ name: "name", placeholder: "请输入负责人名称" }],
    buttons: ["取消", { text: "保存", role: "confirm" }],
  });
  await a.present();
  const r = await a.onDidDismiss();
  const name = String(r.data?.values?.name || "").trim();
  if (r.role !== "confirm" || !name) return;
  try {
    await api("/task-bookkeeping/owners", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    await load();
  } catch (e) {
    fail(e);
  }
};
const remove = async (o: Owner) => {
  const a = await alertController.create({
    header: "删除确认",
    message: `“${o.name}”已关联 ${counts.value.get(o.name) || 0} 条历史任务。删除名单不会删除历史数据，确认继续吗？`,
    buttons: [
      "取消",
      {
        text: "删除",
        role: "destructive",
        handler: async () => {
          try {
            await api(`/task-bookkeeping/owners/${o.id}`, { method: "DELETE" });
            await load();
          } catch (e) {
            fail(e);
          }
        },
      },
    ],
  });
  await a.present();
};
onMounted(load);
</script>
<template>
  <IonPage
    ><PageHeader
      title="负责人管理"
      subtitle="任务负责人基础资料"
      back
    /><IonContent
      ><IonRefresher slot="fixed" @ion-refresh="load"
        ><IonRefresherContent
      /></IonRefresher>
      <main>
        <section class="summary">
          <div>
            <span>负责人</span><strong>{{ owners.length }}</strong>
          </div>
          <div>
            <span>关联任务</span><strong>{{ tasks.length }}</strong>
          </div>
        </section>
        <div class="toolbar">
          <IonSearchbar
            v-model="query"
            placeholder="搜索负责人名称"
            mode="ios"
          /><button @click="add">新增负责人</button>
        </div>
        <section class="list">
          <article v-for="o in filtered" :key="o.id">
            <div class="initial">{{ o.name.slice(0, 1) }}</div>
            <div>
              <h2>{{ o.name }}</h2>
              <p>
                已关联 {{ counts.get(o.name) || 0 }} 条任务 ·
                {{ String(o.created_at || "").slice(0, 10) || "暂无创建时间" }}
              </p>
            </div>
            <button class="danger" @click="remove(o)">删除</button>
          </article>
          <div v-if="!filtered.length && !loading" class="empty-state">
            没有匹配的负责人
          </div>
        </section>
      </main></IonContent
    ></IonPage
  >
</template>
<style scoped>
main {
  padding: 12px;
}
.summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.summary div {
  padding: 14px;
  border: 1px solid var(--app-line);
  background: var(--app-card);
}
.summary span,
.summary strong {
  display: block;
}
.summary span {
  color: var(--app-muted);
  font-size: 12px;
}
.summary strong {
  margin-top: 5px;
  font-size: 24px;
}
.toolbar {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: center;
  margin: 12px 0;
}
.toolbar ion-searchbar {
  --background: var(--app-card);
  --box-shadow: none;
  padding: 0;
}
.toolbar button {
  height: 44px;
  border: 0;
  border-radius: 10px;
  color: #fff;
  background: #2563eb;
}
.list {
  border: 1px solid var(--app-line);
  background: var(--app-card);
}
article {
  display: grid;
  grid-template-columns: 38px 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 13px;
  border-bottom: 1px solid var(--app-line);
}
article:last-child {
  border-bottom: 0;
}
.initial {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  color: #2563eb;
  background: #eaf2ff;
  font-weight: 700;
}
h2,
p {
  margin: 0;
}
h2 {
  font-size: 15px;
}
p {
  margin-top: 5px;
  color: var(--app-muted);
  font-size: 11px;
}
.danger {
  padding: 7px;
  border: 0;
  color: #dc2626;
  background: transparent;
}
</style>
