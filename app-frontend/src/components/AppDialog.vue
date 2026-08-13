<script setup lang="ts">
import { ref, watch } from "vue";
const props = withDefaults(defineProps<{ open: boolean; title: string; value?: string; multiline?: boolean; confirmText?: string; cancelText?: string; readonly?: boolean; confirmOnly?: boolean }>(), { value: "", multiline: false, confirmText: "确定", cancelText: "取消", readonly: false, confirmOnly: false });
const emit = defineEmits<{ (e: "close"): void; (e: "confirm", value: string): void }>();
const input = ref(props.value);
watch(() => [props.open, props.value], () => { if (props.open) input.value = props.value; });
</script>
<template>
  <div v-if="open" class="app-dialog-mask" @click.self="emit('close')">
    <section class="app-dialog" role="dialog" aria-modal="true">
      <header><b>{{ title }}</b><button type="button" aria-label="关闭" @click="emit('close')">关闭</button></header>
      <p v-if="confirmOnly" class="message">{{ value }}</p>
      <textarea v-else-if="multiline && !readonly" v-model="input" rows="5" autofocus />
      <input v-else-if="!readonly" v-model="input" autofocus @keyup.enter="emit('confirm', input.trim())" />
      <pre v-else>{{ value }}</pre>
      <footer><button type="button" @click="emit('close')">{{ cancelText }}</button><button type="button" class="primary" @click="emit('confirm', input.trim())">{{ confirmText }}</button></footer>
    </section>
  </div>
</template>
<style scoped>
.app-dialog-mask{position:fixed;inset:0;z-index:3000;display:flex;align-items:flex-end;background:#0f172a66}.app-dialog{width:100%;max-height:min(80vh,80dvh);overflow:auto;padding:0 14px calc(18px + env(safe-area-inset-bottom));border-radius:16px 16px 0 0;background:var(--app-card)}.app-dialog header{position:sticky;top:0;z-index:1;display:flex;align-items:center;justify-content:space-between;min-height:52px;background:var(--app-card)}.app-dialog header button{border:0;color:var(--app-blue);background:transparent;font-size:14px}.app-dialog input,.app-dialog textarea{display:block;width:100%;padding:12px;border:0;border-radius:10px;outline:0;color:var(--app-text);background:var(--ion-background-color);font:16px/1.5 inherit}.app-dialog textarea{resize:vertical}.app-dialog pre,.app-dialog .message{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;padding:12px;border-radius:10px;color:var(--app-text);background:var(--ion-background-color);font:13px/1.6 inherit}.app-dialog footer{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:14px}.app-dialog footer button{min-height:44px;border:1px solid var(--app-line);border-radius:10px;color:var(--app-text);background:var(--app-card);font-size:14px}.app-dialog footer .primary{border-color:var(--app-blue);color:#fff;background:var(--app-blue)}
</style>
