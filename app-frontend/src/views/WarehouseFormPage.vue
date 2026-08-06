<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { IonContent, IonPage, toastController } from "@ionic/vue";
import { useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { api, ApiError } from "../api";

type Row = Record<string, any>;
const route = useRoute();
const router = useRouter();
const kind = computed(() => String(route.params.kind));
const id = computed(() => (route.params.id ? Number(route.params.id) : 0));
const saving = ref(false);
const productImage = ref<File | null>(null);
const warehouses = ref<Row[]>([]);
const products = ref<Row[]>([]);
const form = reactive<Row>({
  code: "",
  name: "",
  address: "",
  contact_name: "",
  contact_phone: "",
  is_active: true,
  remark: "",
  sku: "",
  barcode: "",
  specification: "",
  unit: "件",
  cost_price: 0,
  warning_quantity: 0,
  warehouse_id: "",
  source_type: "purchase",
  supplier: "",
  external_order_no: "",
  delivery_method: "shipping",
  recipient_name: "",
  recipient_phone: "",
  recipient_address: "",
  carrier: "",
  tracking_no: "",
  items: [{ product_id: "", quantity: 1 }],
});
const titles: Record<string, string> = {
  warehouse: "仓库",
  product: "商品",
  inbound: "入库单",
  outbound: "出库单",
};
const pageTitle = computed(
  () => `${id.value ? "编辑" : "新增"}${titles[kind.value] || "仓储记录"}`,
);

function addItem() {
  form.items.push({ product_id: "", quantity: 1 });
}
function removeItem(index: number) {
  if (form.items.length > 1) form.items.splice(index, 1);
}
async function load() {
  try {
    [warehouses.value, products.value] = await Promise.all([
      api<Row[]>("/warehouse/warehouses"),
      api<Row[]>("/warehouse/products"),
    ]);
    if (id.value && kind.value === "warehouse")
      Object.assign(
        form,
        warehouses.value.find((item) => item.id === id.value) || {},
      );
    if (id.value && kind.value === "product")
      Object.assign(
        form,
        products.value.find((item) => item.id === id.value) || {},
      );
    if (id.value && kind.value === "inbound") {
      const orders = await api<Row[]>("/warehouse/inbound-orders");
      const order = orders.find((item) => item.id === id.value);
      if (order)
        Object.assign(form, order, {
          items: (order.items || []).map((item: Row) => ({
            product_id: item.product_id,
            quantity: item.quantity,
          })),
        });
    }
  } catch (error) {
    await showError(error, "基础资料加载失败");
  }
}
async function showError(error: unknown, fallback: string) {
  const toast = await toastController.create({
    message: error instanceof ApiError ? error.detail : fallback,
    duration: 2300,
    color: "danger",
  });
  await toast.present();
}
async function save() {
  if (saving.value) return;
  saving.value = true;
  try {
    let path = "";
    let method = "POST";
    let payload: Row = {};
    if (kind.value === "warehouse") {
      path = id.value
        ? `/warehouse/warehouses/${id.value}`
        : "/warehouse/warehouses";
      method = id.value ? "PUT" : "POST";
      payload = {
        code: form.code,
        name: form.name,
        address: form.address || null,
        contact_name: form.contact_name || null,
        contact_phone: form.contact_phone || null,
        is_active: form.is_active,
        remark: form.remark || null,
      };
    } else if (kind.value === "product") {
      path = id.value
        ? `/warehouse/products/${id.value}`
        : "/warehouse/products";
      method = id.value ? "PUT" : "POST";
      payload = {
        sku: form.sku,
        name: form.name,
        barcode: form.barcode || null,
        specification: form.specification || null,
        unit: form.unit || "件",
        cost_price: Number(form.cost_price || 0),
        warning_quantity: Number(form.warning_quantity || 0),
        is_active: form.is_active,
        remark: form.remark || null,
      };
    } else if (kind.value === "inbound") {
      path = id.value
        ? `/warehouse/inbound-orders/${id.value}`
        : "/warehouse/inbound-orders";
      method = id.value ? "PUT" : "POST";
      payload = {
        warehouse_id: Number(form.warehouse_id),
        source_type: form.source_type,
        supplier: form.supplier || null,
        remark: form.remark || null,
        items: form.items.map((item: Row) => ({
          product_id: Number(item.product_id),
          quantity: Number(item.quantity),
        })),
      };
    } else {
      path = "/warehouse/outbound-orders";
      payload = {
        warehouse_id: Number(form.warehouse_id),
        external_order_no: form.external_order_no || null,
        delivery_method: form.delivery_method,
        recipient_name: form.recipient_name || null,
        recipient_phone: form.recipient_phone || null,
        recipient_address: form.recipient_address || null,
        carrier: form.carrier || null,
        tracking_no: form.tracking_no || null,
        remark: form.remark || null,
        items: form.items.map((item: Row) => ({
          product_id: Number(item.product_id),
          quantity: Number(item.quantity),
        })),
      };
    }
    const saved = await api<Row>(path, {
      method,
      body: JSON.stringify(payload),
    });
    if (kind.value === "product" && productImage.value) {
      const image = new FormData();
      image.append("image", productImage.value);
      const productId = id.value || saved.id;
      const response = await fetch(`/warehouse/products/${productId}/image`, {
        method: "POST",
        credentials: "include",
        body: image,
      });
      if (!response.ok) throw new Error("商品图片上传失败");
    }
    const toast = await toastController.create({
      message: "保存成功",
      duration: 1400,
      color: "success",
    });
    await toast.present();
    router.back();
  } catch (error) {
    await showError(error, "保存失败");
  } finally {
    saving.value = false;
  }
}
onMounted(load);
</script>

<template>
  <IonPage
    ><PageHeader :title="pageTitle" subtitle="填写后保存" back /><IonContent
      ><main class="warehouse-form">
        <section v-if="kind === 'warehouse'" class="form-section">
          <label
            >仓库编码<input
              v-model="form.code"
              placeholder="例如：WH001" /></label
          ><label
            >仓库名称<input
              v-model="form.name"
              placeholder="输入仓库名称" /></label
          ><label
            >仓库地址<input v-model="form.address" placeholder="输入详细地址"
          /></label>
          <div class="form-grid">
            <label>联系人<input v-model="form.contact_name" /></label
            ><label
              >联系电话<input v-model="form.contact_phone" inputmode="tel"
            /></label>
          </div>
          <label class="switch-row"
            ><span>启用仓库</span
            ><input v-model="form.is_active" type="checkbox"
          /></label>
        </section>
    <section v-else-if="kind === 'product'" class="form-section">
      <label>商品图片<input type="file" accept="image/jpeg,image/png,image/webp" @change="productImage = ($event.target as HTMLInputElement).files?.[0] || null" /></label>
          <div class="form-grid">
            <label>商品 SKU<input v-model="form.sku" /></label
            ><label>商品名称<input v-model="form.name" /></label>
          </div>
          <div class="form-grid">
            <label>条码<input v-model="form.barcode" /></label
            ><label>规格<input v-model="form.specification" /></label>
          </div>
          <div class="form-grid">
            <label>单位<input v-model="form.unit" /></label
            ><label
              >成本价<input
                v-model.number="form.cost_price"
                inputmode="decimal"
                type="number"
                min="0"
            /></label>
          </div>
          <label
            >库存预警数量<input
              v-model.number="form.warning_quantity"
              inputmode="numeric"
              type="number"
              min="0" /></label
          ><label class="switch-row"
            ><span>启用商品</span
            ><input v-model="form.is_active" type="checkbox"
          /></label>
        </section>
        <section v-else class="form-section">
          <label
            >选择仓库<select v-model="form.warehouse_id">
              <option value="">请选择</option>
              <option
                v-for="item in warehouses.filter(
                  (row) => row.is_active !== false,
                )"
                :key="item.id"
                :value="item.id"
              >
                {{ item.name }}
              </option>
            </select></label
          ><template v-if="kind === 'inbound'"
            ><label
              >入库来源<select v-model="form.source_type">
                <option value="purchase">采购入库</option>
                <option value="return">退货入库</option>
                <option value="other">其他入库</option>
              </select></label
            ><label>供应商<input v-model="form.supplier" /></label></template
          ><template v-else
            ><label>外部订单号<input v-model="form.external_order_no" /></label
            ><label
              >交付方式<select v-model="form.delivery_method">
                <option value="shipping">快递发货</option>
                <option value="pickup">到店自提</option>
              </select></label
            >
            <div class="form-grid">
              <label>收件人<input v-model="form.recipient_name" /></label
              ><label
                >联系电话<input v-model="form.recipient_phone" inputmode="tel"
              /></label>
            </div>
            <label
              >收件地址<textarea
                v-model="form.recipient_address"
                rows="2"
              ></textarea></label
          ></template>
        </section>
        <section
          v-if="kind === 'inbound' || kind === 'outbound'"
          class="form-section"
        >
          <div class="items-title">
            <b>商品明细</b><button @click="addItem">添加商品</button>
          </div>
          <div
            v-for="(item, index) in form.items"
            :key="index"
            class="item-line"
          >
            <select v-model="item.product_id">
              <option value="">选择商品</option>
              <option
                v-for="product in products.filter(
                  (row) => row.is_active !== false,
                )"
                :key="product.id"
                :value="product.id"
              >
                {{ product.sku }} · {{ product.name }}
              </option></select
            ><input
              v-model.number="item.quantity"
              type="number"
              inputmode="numeric"
              min="1"
            /><button @click="removeItem(Number(index))">删除</button>
          </div>
        </section>
        <section class="form-section">
          <label
            >备注<textarea
              v-model="form.remark"
              rows="3"
              placeholder="选填"
            ></textarea>
          </label>
        </section></main
    ></IonContent>
    <footer class="form-footer">
      <button @click="router.back()">取消</button
      ><button class="primary" :disabled="saving" @click="save">
        {{ saving ? "保存中…" : "保存" }}
      </button>
    </footer></IonPage
  >
</template>

<style scoped>
.warehouse-form {
  padding: 12px 14px 110px;
}
.form-section {
  margin-bottom: 12px;
  padding: 16px;
  border: 1px solid var(--app-line);
  border-radius: 16px;
  background: var(--app-card);
}
label {
  display: block;
  margin-bottom: 15px;
  color: var(--app-muted);
  font-size: 13px;
}
label:last-child {
  margin-bottom: 0;
}
input,
select,
textarea {
  box-sizing: border-box;
  width: 100%;
  margin-top: 7px;
  padding: 12px;
  border: 1px solid var(--app-line);
  border-radius: 11px;
  outline: 0;
  color: var(--app-text);
  background: var(--ion-background-color);
  font: 16px inherit;
}
textarea {
  resize: vertical;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--app-text);
}
.switch-row input {
  width: 22px;
  height: 22px;
  margin: 0;
}
.items-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.items-title button,
.item-line button {
  border: 0;
  border-radius: 9px;
  padding: 8px 10px;
  color: #1677ff;
  background: #eaf4ff;
}
.item-line {
  display: grid;
  grid-template-columns: 1fr 72px auto;
  gap: 7px;
  margin: 8px 0;
}
.item-line input,
.item-line select {
  margin: 0;
}
.item-line button {
  color: #ef4444;
  background: #fee2e2;
}
.form-footer {
  position: relative;
  z-index: 5;
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 10px;
  padding: 10px 14px calc(10px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--app-line);
  background: var(--app-card);
}
.form-footer button {
  height: 46px;
  border: 1px solid var(--app-line);
  border-radius: 13px;
  color: var(--app-text);
  background: transparent;
  font-size: 16px;
  font-weight: 600;
}
.form-footer .primary {
  color: #fff;
  border-color: #1677ff;
  background: #1677ff;
}
.ion-palette-dark .items-title button {
  background: #142b49;
}
.ion-palette-dark .item-line button {
  background: #451a1a;
}
@media (max-width: 380px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .item-line {
    grid-template-columns: 1fr 64px;
  }
  .item-line button {
    grid-column: 1/3;
  }
}
</style>
