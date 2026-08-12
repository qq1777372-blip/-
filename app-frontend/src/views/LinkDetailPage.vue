<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  IonContent,
  IonIcon,
  IonModal,
  IonPage,
  alertController,
  toastController,
} from "@ionic/vue";
import {
  addOutline,
  chevronBackOutline,
  chevronForwardOutline,
  closeOutline,
  copyOutline,
  createOutline,
  openOutline,
  removeOutline,
  trashOutline,
} from "ionicons/icons";
import { useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { api, ApiError } from "../api";
import { session } from "../session";
import type { SavedLink } from "./LinkPlazaPage.vue";
// The editor preview uses this same parser, so preview and reader stay identical.
import { normalizePath, parseContent } from "../markdown";

const route = useRoute();
const router = useRouter();
const item = ref<SavedLink | null>(null);
const loading = ref(true);
const canEdit = computed(
  () =>
    session.user?.role === "superadmin" ||
    item.value?.author_user_id === session.user?.id,
);
const contentBlocks = computed(() =>
  parseContent(item.value?.description, item.value?.title || "帖子图片"),
);
const referencedImages = computed(
  () =>
    new Set(
      contentBlocks.value
        .filter((block) => block.type === "image")
        .map((block) => normalizePath(block.src)),
    ),
);
const remainingImages = computed(
  () =>
    item.value?.images?.filter(
      (image) => !referencedImages.value.has(normalizePath(image.url)),
    ) || [],
);
const previewImages = computed(() => {
  const images = [
    ...contentBlocks.value
      .filter((block) => block.type === "image")
      .map((block) => ({ url: block.src, alt: block.alt })),
    ...remainingImages.value.map((image) => ({
      url: image.url,
      alt: image.name || item.value?.title || "帖子图片",
    })),
  ];
  return images.filter(
    (image, index) =>
      images.findIndex(
        (candidate) =>
          normalizePath(candidate.url) === normalizePath(image.url),
      ) === index,
  );
});
const previewIndex = ref(-1);
const previewImage = computed(
  () => previewImages.value[previewIndex.value] || null,
);
const previewZoom = ref(1);
const pan = ref({ x: 0, y: 0 });
const dragging = ref(false);
const dragStart = ref({ x: 0, y: 0, panX: 0, panY: 0 });

function openImage(url?: string) {
  if (!url) return;
  const index = previewImages.value.findIndex(
    (image) => normalizePath(image.url) === normalizePath(url),
  );
  previewIndex.value = index < 0 ? 0 : index;
  previewZoom.value = 1;
  pan.value = { x: 0, y: 0 };
}
function closeImage() {
  previewIndex.value = -1;
  previewZoom.value = 1;
  pan.value = { x: 0, y: 0 };
}
function moveImage(step: number) {
  const total = previewImages.value.length;
  if (total > 1) {
    previewIndex.value = (previewIndex.value + step + total) % total;
    previewZoom.value = 1;
    pan.value = { x: 0, y: 0 };
  }
}
function changeZoom(step: number) {
  previewZoom.value = Math.min(
    3,
    Math.max(1, Number((previewZoom.value + step).toFixed(1))),
  );
  if (previewZoom.value === 1) pan.value = { x: 0, y: 0 };
}
function toggleZoom() {
  previewZoom.value = previewZoom.value === 1 ? 2 : 1;
  if (previewZoom.value === 1) pan.value = { x: 0, y: 0 };
}
function startPan(event: PointerEvent) {
  if (previewZoom.value <= 1 || event.pointerType === 'mouse' && event.button !== 0) return;
  dragging.value = true;
  dragStart.value = { x: event.clientX, y: event.clientY, panX: pan.value.x, panY: pan.value.y };
  (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
}
function movePan(event: PointerEvent) {
  if (!dragging.value) return;
  pan.value = {
    x: dragStart.value.panX + event.clientX - dragStart.value.x,
    y: dragStart.value.panY + event.clientY - dragStart.value.y,
  };
}
function endPan() {
  dragging.value = false;
}

async function load() {
  try {
    const rows = await api<SavedLink[]>("/saved-links");
    item.value = rows.find((row) => row.id === Number(route.params.id)) || null;
  } catch (error) {
    const toast = await toastController.create({
      message: error instanceof ApiError ? error.detail : "帖子加载失败",
      duration: 2200,
      color: "danger",
    });
    await toast.present();
  } finally {
    loading.value = false;
  }
}
async function copyLink() {
  if (!item.value?.url) return;
  try {
    await navigator.clipboard.writeText(item.value.url);
    const toast = await toastController.create({
      message: "链接已复制",
      duration: 1500,
    });
    await toast.present();
  } catch {}
}
function openLink() {
  if (item.value?.url)
    window.open(item.value.url, "_blank", "noopener,noreferrer");
}
function editItem() {
  if (!item.value) return;
  if (item.value.category?.toLowerCase().startsWith("tutorial:"))
    void router.push(`/tabs/form/articles/${item.value.id}`);
  else void router.push(`/tabs/form/links/${item.value.id}`);
}
async function remove() {
  if (!item.value) return;
  const current = item.value;
  const alert = await alertController.create({
    header: "删除帖子",
    message: `确定删除“${current.title}”吗？`,
    buttons: [
      { text: "取消", role: "cancel" },
      {
        text: "删除",
        role: "destructive",
        handler: async () => {
          try {
            await api(`/saved-links/${current.id}`, { method: "DELETE" });
            router.replace("/tabs/links");
          } catch (error) {
            const toast = await toastController.create({
              message: error instanceof ApiError ? error.detail : "删除失败",
              duration: 2000,
              color: "danger",
            });
            await toast.present();
          }
        },
      },
    ],
  });
  await alert.present();
}
function host(url?: string) {
  try {
    return url ? new URL(url).hostname : "";
  } catch {
    return "";
  }
}
function time(value: string) {
  return String(value || "")
    .replace("T", " ")
    .slice(0, 16);
}
function category(value?: string) {
  const text = String(value || "").trim();
  return !text || text.toLowerCase().startsWith("tutorial:") ? "未分类" : text;
}
function pushLabel(value?: string) {
  return value === "scheduled"
    ? "已定时"
    : value === "sending"
      ? "推送中"
      : value === "sent"
        ? "已推送"
        : value === "failed"
          ? "推送失败"
          : "";
}
onMounted(load);
</script>

<template>
  <IonPage>
    <PageHeader title="帖子详情" subtitle="链接广场" back />
    <IonContent>
      <main v-if="item" class="link-reader-page">
        <article class="link-reader-post">
          <header class="link-reader-author">
            <div class="link-reader-identity">
              <div>
                <strong>{{ item.author_username }}</strong
                ><span>{{ category(item.category) }}</span
                ><em
                  v-if="pushLabel(item.push_status)"
                  :class="`status-${item.push_status}`"
                  >{{ pushLabel(item.push_status) }}</em
                >
              </div>
              <small
                >{{ time(item.updated_at || item.created_at)
                }}<template v-if="item.url"> · {{ host(item.url) }}</template
                ><template v-if="item.images?.length">
                  · {{ item.images.length }} 张图</template
                ></small
              >
            </div>
          </header>

          <h1>{{ item.title }}</h1>
          <div v-if="contentBlocks.length" class="link-reader-content">
            <template v-for="(block, index) in contentBlocks" :key="index">
              <p
                v-if="block.type === 'paragraph'"
                :class="`align-${block.align}`"
              >
                <template
                  v-for="(segment, segmentIndex) in block.segments"
                  :key="segmentIndex"
                  ><a
                    v-if="segment.type === 'link'"
                    :href="segment.value"
                    target="_blank"
                    rel="noopener noreferrer"
                    >{{ segment.label }}</a
                  ><span v-else>{{ segment.value }}</span></template
                >
              </p>
              <figure v-else :class="`align-${block.align}`">
                <button
                  class="link-reader-image-button"
                  type="button"
                  aria-label="查看大图"
                  @click="openImage(block.src)"
                >
                  <img :src="block.src" :alt="block.alt" loading="lazy" decoding="async" />
                </button>
              </figure>
            </template>
          </div>

          <button v-if="item.url" class="link-reader-url" @click="openLink">
            <strong>{{ host(item.url) }}</strong
            ><span>{{ item.url }}</span
            ><IonIcon :icon="openOutline" />
          </button>
          <section v-if="remainingImages.length" class="link-reader-gallery">
            <button
              v-for="image in remainingImages"
              :key="image.storage_name"
              class="link-reader-image-button"
              type="button"
              aria-label="查看大图"
              @click="openImage(image.url)"
            >
              <img :src="image.url" :alt="image.name || item.title" loading="lazy" decoding="async" />
            </button>
          </section>

          <footer class="link-reader-footer">
            <span>帖子 #{{ item.id }}</span>
            <div>
              <button v-if="item.url" @click="copyLink">
                <IonIcon :icon="copyOutline" />复制链接</button
              ><button v-if="canEdit" @click="editItem">
                <IonIcon :icon="createOutline" />编辑</button
              ><button v-if="canEdit" class="danger" @click="remove">
                <IonIcon :icon="trashOutline" />删除
              </button>
            </div>
          </footer>
        </article>
      </main>
      <div v-else-if="!loading" class="empty-state">帖子不存在或已删除</div>
    </IonContent>
    <IonModal
      :is-open="Boolean(previewImage)"
      css-class="link-image-preview-modal"
      @did-dismiss="closeImage"
    >
      <div class="link-image-preview" @click.self="closeImage">
        <button
          class="link-image-preview__close"
          type="button"
          aria-label="关闭图片预览"
          @click="closeImage"
        >
          <IonIcon :icon="closeOutline" />
        </button>
        <button
          v-if="previewImages.length > 1"
          class="link-image-preview__nav link-image-preview__nav--prev"
          type="button"
          aria-label="上一张"
          @click="moveImage(-1)"
        >
          <IonIcon :icon="chevronBackOutline" />
        </button>
        <button
          class="link-image-preview__zoom link-image-preview__zoom--out"
          type="button"
          aria-label="缩小图片"
          @click="changeZoom(-0.5)"
        >
          <IonIcon :icon="removeOutline" />
        </button>
        <img
          v-if="previewImage"
          :src="previewImage.url"
          :alt="previewImage.alt"
          :style="previewZoom > 1 ? { width: `${previewZoom * 100}%`, maxWidth: 'none', maxHeight: 'none', transform: `translate(${pan.x}px, ${pan.y}px)` } : { transform: 'none' }"
          :class="{ dragging }"
          @pointerdown="startPan"
          @pointermove="movePan"
          @pointerup="endPan"
          @pointercancel="endPan"
          @pointerleave="endPan"
          @dblclick="toggleZoom"
        />
        <button
          class="link-image-preview__zoom link-image-preview__zoom--in"
          type="button"
          aria-label="放大图片"
          @click="changeZoom(0.5)"
        >
          <IonIcon :icon="addOutline" />
        </button>
        <span class="link-image-preview__zoom-level"
          >{{ Math.round(previewZoom * 100) }}%</span
        >
        <button
          v-if="previewImages.length > 1"
          class="link-image-preview__nav link-image-preview__nav--next"
          type="button"
          aria-label="下一张"
          @click="moveImage(1)"
        >
          <IonIcon :icon="chevronForwardOutline" />
        </button>
        <span v-if="previewImages.length > 1" class="link-image-preview__count"
          >{{ previewIndex + 1 }} / {{ previewImages.length }}</span
        >
      </div>
    </IonModal>
  </IonPage>
</template>

<style scoped>
.link-reader-page {
  min-height: 100%;
  padding: 0 16px 44px;
  background: var(--app-card);
}
.link-reader-post {
  max-width: 720px;
  margin: 0 auto;
  padding: 16px 0;
}
.link-reader-author {
  display: flex;
  align-items: center;
  gap: 9px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--app-line);
}
.link-reader-avatar {
  width: 30px;
  height: 30px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 50%;
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  font-size: 12px;
  font-weight: 800;
}
.link-reader-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.link-reader-identity {
  min-width: 0;
  flex: 1;
}
.link-reader-identity > div {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.link-reader-identity strong {
  font-size: 13px;
}
.link-reader-identity span,
.link-reader-identity em {
  padding: 3px 7px;
  border-radius: 999px;
  color: var(--app-muted);
  background: var(--app-soft);
  font-size: 10px;
  font-style: normal;
}
.link-reader-identity em.status-sent {
  color: #047857;
  background: #ecfdf5;
}
.link-reader-identity em.status-failed {
  color: #b91c1c;
  background: #fef2f2;
}
.link-reader-identity small {
  display: block;
  margin-top: 3px;
  color: var(--app-muted);
  font-size: 11px;
}
.link-reader-post h1 {
  margin: 16px 0 10px;
  color: var(--app-text);
  font-size: 22px;
  line-height: 1.4;
}
.link-reader-content {
  color: var(--app-text);
  overflow-wrap: anywhere;
  font-size: 15px;
  line-height: 1.75;
}
.link-reader-content p {
  margin: 0 0 13px;
  white-space: pre-wrap;
}
.link-reader-content .align-left {
  text-align: left;
}
.link-reader-content .align-center {
  text-align: center;
}
.link-reader-content .align-right {
  text-align: right;
}
.link-reader-content a {
  color: #1677ff;
  text-decoration: none;
}
.link-reader-content figure {
  margin: 12px 0;
}
.link-reader-content figure img {
  display: block;
  max-width: 100%;
  height: auto;
  border-radius: 9px;
  background: var(--app-soft);
}
.link-reader-content figure.align-center .link-reader-image-button {
  margin-inline: auto;
}
.link-reader-content figure.align-right .link-reader-image-button {
  margin-left: auto;
}
.link-reader-image-button {
  display: block;
  max-width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: zoom-in;
}
.link-reader-image-button img {
  pointer-events: none;
}
.link-reader-url {
  width: 100%;
  margin-top: 14px;
  padding: 11px 38px 11px 12px;
  position: relative;
  display: grid;
  gap: 3px;
  border: 1px solid var(--app-line);
  border-radius: 10px;
  text-align: left;
  color: var(--app-text);
  background: var(--app-soft);
  font: inherit;
}
.link-reader-url strong {
  font-size: 12px;
}
.link-reader-url span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #1677ff;
  font-size: 11px;
}
.link-reader-url ion-icon {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #1677ff;
  font-size: 18px;
}
.link-reader-gallery {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}
.link-reader-gallery img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 9px;
  background: var(--app-soft);
}
.link-image-preview-modal {
  --width: 100%;
  --height: 100%;
  --border-radius: 0;
  --background: #050505;
}
.link-image-preview {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
  padding: 56px 52px;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  background: #050505;
  touch-action: none;
}
.link-image-preview > img {
  display: block;
  width: auto;
  max-width: min(100%, 1200px);
  max-height: calc(100vh - 112px);
  flex: 0 0 auto;
  object-fit: contain;
  transition: transform 0.2s ease;
  cursor: zoom-in;
  user-select: none;
  touch-action: none;
}
.link-image-preview > img.dragging {
  cursor: grabbing;
  transition: none;
}
.link-image-preview > img:active {
  cursor: grabbing;
}
.link-image-preview button {
  position: absolute;
  z-index: 2;
  width: 44px;
  height: 44px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: #1f1f1fcc;
}
.link-image-preview button ion-icon {
  font-size: 27px;
}
.link-image-preview__close {
  top: calc(env(safe-area-inset-top, 0px) + 12px);
  right: 14px;
}
.link-image-preview__nav {
  top: 50%;
  transform: translateY(-50%);
}
.link-image-preview__nav--prev {
  left: 8px;
}
.link-image-preview__nav--next {
  right: 8px;
}
.link-image-preview__zoom {
  bottom: calc(env(safe-area-inset-bottom, 0px) + 16px);
}
.link-image-preview__zoom--out {
  left: calc(50% - 98px);
}
.link-image-preview__zoom--in {
  right: calc(50% - 98px);
}
.link-image-preview__zoom-level {
  position: absolute;
  bottom: calc(env(safe-area-inset-bottom, 0px) + 27px);
  left: 50%;
  transform: translateX(-50%);
  color: #fff;
  font-size: 12px;
}
.link-image-preview__count {
  position: absolute;
  bottom: calc(env(safe-area-inset-bottom, 0px) + 70px);
  left: 50%;
  transform: translateX(-50%);
  padding: 5px 10px;
  border-radius: 999px;
  color: #fff;
  background: #1f1f1fcc;
  font-size: 12px;
}
.link-reader-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px solid var(--app-line);
  color: var(--app-muted);
  font-size: 11px;
}
.link-reader-footer > div {
  display: flex;
  gap: 2px;
}
.link-reader-footer button {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 6px;
  border: 0;
  color: #4f60e8;
  background: transparent;
  font: inherit;
  font-size: 11px;
}
.link-reader-footer button.danger {
  color: #ef4444;
}
.ion-palette-dark .link-reader-identity em.status-sent {
  color: #6ee7b7;
  background: #064e3b;
}
.ion-palette-dark .link-reader-identity em.status-failed {
  color: #fca5a5;
  background: #450a0a;
}
</style>
