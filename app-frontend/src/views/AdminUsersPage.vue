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
type Level = "none" | "read" | "write";
type User = {
  id: number;
  username: string;
  display_name?: string;
  role: string;
  is_active: boolean;
  permissions: Record<string, Level>;
  created_at?: string;
};
const modules = [
  ["dashboard", "运营工作台", "统计、提醒与全局搜索"],
  ["links", "链接广场", "链接、文章与图片管理"],
  ["task_bookkeeping", "任务记账", "任务、负责人和店铺资料"],
  ["dingtalk_profits", "钉钉利润", "利润统计与明细"],
  ["shop_records", "店铺账号", "店铺档案与自定义字段"],
  ["peer_shops", "同行店铺", "同行链接与截图"],
  ["licenses", "执照档案", "执照资料、图片和字段"],
  ["account_usage", "账号使用记录", "账号分配与敏感信息"],
  ["mobile_devices", "手机设备", "设备资料与状态"],
  ["warehouse", "仓储与发货", "仓库、商品、出入库与流水"],
] as const;
const users = ref<User[]>([]),
  query = ref(""),
  loading = ref(true),
  editor = ref<User | null>(null),
  creating = ref(false),
  saving = ref(false);
const access = reactive<{ role: string; permissions: Record<string, Level> }>({
  role: "editor",
  permissions: {},
});
const create = reactive({ username: "", password: "", role: "editor" });
const filtered = computed(() =>
  users.value.filter((u) =>
    `${u.username}${u.display_name || ""}`
      .toLowerCase()
      .includes(query.value.toLowerCase()),
  ),
);
const roleName = (r: string) =>
  r === "superadmin" ? "超级管理员" : r === "editor" ? "编辑员" : "只读账号";
const fail = async (e: unknown) => {
  const t = await toastController.create({
    message: e instanceof ApiError ? e.detail : "操作失败",
    duration: 2200,
    color: "danger",
  });
  await t.present();
};
const load = async () => {
  try {
    users.value = await api("/admin-users");
  } catch (e) {
    fail(e);
  } finally {
    loading.value = false;
  }
};
const defaults = (role: string): Record<string, Level> =>
  Object.fromEntries(
    modules.map((m) => [m[0], role === "viewer" ? "read" : "write"]),
  );
const openAccess = (u: User) => {
  editor.value = u;
  access.role = u.role;
  access.permissions = { ...defaults(u.role), ...u.permissions };
};
const roleChanged = () => {
  if (access.role !== "superadmin") access.permissions = defaults(access.role);
};
const saveAccess = async () => {
  if (!editor.value) return;
  saving.value = true;
  try {
    await api(`/admin-users/${editor.value.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        role: access.role,
        permissions: access.permissions,
      }),
    });
    editor.value = null;
    await load();
  } catch (e) {
    fail(e);
  } finally {
    saving.value = false;
  }
};
const createUser = async () => {
  if (!create.username.trim() || create.password.length < 8) {
    return fail(new Error("请填写账号和至少 8 位密码"));
  }
  saving.value = true;
  try {
    await api("/admin-users", {
      method: "POST",
      body: JSON.stringify({
        username: create.username.trim(),
        password: create.password,
        role: create.role,
        permissions: defaults(create.role),
      }),
    });
    creating.value = false;
    Object.assign(create, { username: "", password: "", role: "editor" });
    await load();
  } catch (e) {
    fail(e);
  } finally {
    saving.value = false;
  }
};
const toggle = async (u: User) => {
  try {
    await api(`/admin-users/${u.id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: !u.is_active }),
    });
    await load();
  } catch (e) {
    fail(e);
  }
};
const password = async (u: User) => {
  const a = await alertController.create({
    header: `修改 ${u.username} 的密码`,
    inputs: [
      {
        name: "new_password",
        type: "password",
        placeholder: "至少 8 位新密码",
      },
      { name: "confirm", type: "password", placeholder: "再次输入新密码" },
    ],
    buttons: ["取消", { text: "确认修改", role: "confirm" }],
  });
  await a.present();
  const r = await a.onDidDismiss();
  if (r.role !== "confirm") return;
  const v = r.data.values;
  if (v.new_password !== v.confirm || String(v.new_password).length < 8)
    return fail(new Error("两次密码不一致或少于 8 位"));
  try {
    await api(`/admin-users/${u.id}/password`, {
      method: "PATCH",
      body: JSON.stringify({ new_password: v.new_password }),
    });
    const t = await toastController.create({
      message: "密码已修改",
      duration: 1500,
      color: "success",
    });
    await t.present();
  } catch (e) {
    fail(e);
  }
};
onMounted(load);
</script>
<template>
  <IonPage
    ><PageHeader
      title="账号与权限"
      subtitle="后台账号及模块访问权限"
      back
    /><IonContent
      ><main>
        <section class="stats">
          <div>
            <span>后台账号</span><b>{{ users.length }}</b>
          </div>
          <div>
            <span>已启用</span
            ><b>{{ users.filter((u) => u.is_active).length }}</b>
          </div>
          <div>
            <span>可编辑</span
            ><b>{{ users.filter((u) => u.role !== "viewer").length }}</b>
          </div>
        </section>
        <div class="toolbar">
          <IonSearchbar
            v-model="query"
            placeholder="搜索账号或姓名"
            mode="ios"
          /><button @click="creating = true">新增账号</button>
        </div>
        <section class="users">
          <article v-for="u in filtered" :key="u.id">
            <header>
              <div>
                <h2>{{ u.display_name || u.username }}</h2>
                <p>{{ u.username }} · {{ roleName(u.role) }}</p>
              </div>
              <span :class="{ off: !u.is_active }">{{
                u.is_active ? "启用" : "禁用"
              }}</span>
            </header>
            <p class="scope">
              {{
                u.role === "superadmin"
                  ? "全部模块"
                  : `${Object.values(u.permissions || {}).filter((v) => v === "write").length} 个可编辑 · ${Object.values(u.permissions || {}).filter((v) => v === "read").length} 个只读`
              }}
            </p>
            <footer>
              <button @click="openAccess(u)">修改权限</button
              ><button @click="password(u)">修改密码</button
              ><button class="warn" @click="toggle(u)">
                {{ u.is_active ? "禁用" : "启用" }}
              </button>
            </footer>
          </article>
          <div v-if="!filtered.length && !loading" class="empty-state">
            暂无后台账号
          </div>
        </section>
      </main>
      <div v-if="creating" class="sheet">
        <section>
          <h2>新增后台账号</h2>
          <label
            >登录账号<input
              v-model="create.username"
              autocomplete="off" /></label
          ><label
            >初始密码<input v-model="create.password" type="password" /></label
          ><label
            >初始角色<select v-model="create.role">
              <option value="editor">编辑员</option>
              <option value="viewer">只读账号</option>
              <option value="superadmin">超级管理员</option>
            </select></label
          >
          <footer>
            <button @click="creating = false">取消</button
            ><button class="primary" :disabled="saving" @click="createUser">
              创建账号
            </button>
          </footer>
        </section>
      </div>
      <div v-if="editor" class="sheet access">
        <section>
          <h2>修改账号权限</h2>
          <p>{{ editor.username }} · 保存后该账号需要重新登录</p>
          <label
            >账号角色<select v-model="access.role" @change="roleChanged">
              <option value="editor">编辑员</option>
              <option value="viewer">只读账号</option>
              <option value="superadmin">超级管理员</option>
            </select></label
          >
          <div class="permission">
            <article v-for="m in modules" :key="m[0]">
              <div>
                <b>{{ m[1] }}</b
                ><small>{{ m[2] }}</small>
              </div>
              <select
                v-model="access.permissions[m[0]]"
                :disabled="access.role === 'superadmin'"
              >
                <option v-if="m[0] !== 'dashboard'" value="none">不可访问</option>
                <option value="read">只读</option>
                <option value="write">可编辑</option>
              </select>
            </article>
          </div>
          <footer>
            <button @click="editor = null">取消</button
            ><button class="primary" :disabled="saving" @click="saveAccess">
              保存权限
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
  grid-template-columns: repeat(3, 1fr);
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
  margin-top: 5px;
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
.users {
  display: grid;
  gap: 9px;
}
.users > article {
  padding: 14px;
  border: 1px solid var(--app-line);
  background: var(--app-card);
}
header {
  display: flex;
  justify-content: space-between;
}
h2,
p {
  margin: 0;
}
h2 {
  font-size: 16px;
}
header p,
.scope {
  margin-top: 4px;
  color: var(--app-muted);
  font-size: 11px;
}
header span {
  color: #047857;
  font-size: 11px;
}
.off {
  color: #dc2626;
}
article footer {
  display: flex;
  gap: 7px;
  margin-top: 12px;
}
button {
  padding: 8px 10px;
  border: 1px solid var(--app-line);
  border-radius: 8px;
  color: var(--app-text);
  background: transparent;
}
.warn {
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
  width: 100%;
  max-height: 88%;
  overflow: auto;
  padding: 18px 14px calc(18px + env(safe-area-inset-bottom));
  background: var(--app-card);
}
.sheet h2 {
  margin-bottom: 14px;
}
.sheet label {
  display: block;
  margin: 11px 0;
  color: var(--app-muted);
  font-size: 12px;
}
.sheet input,
.sheet select {
  width: 100%;
  box-sizing: border-box;
  margin-top: 6px;
  padding: 12px;
  border: 1px solid var(--app-line);
  color: var(--app-text);
  background: var(--ion-background-color);
}
.sheet > section > footer {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 8px;
  margin-top: 15px;
}
.permission {
  border: 1px solid var(--app-line);
}
.permission article {
  display: grid;
  grid-template-columns: 1fr 110px;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border-bottom: 1px solid var(--app-line);
}
.permission small {
  display: block;
  margin-top: 3px;
  color: var(--app-muted);
  font-size: 10px;
}
.permission select {
  margin: 0;
  padding: 8px;
}
</style>
