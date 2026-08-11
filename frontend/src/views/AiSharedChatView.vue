<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'

const route = useRoute(); const loading = ref(true); const error = ref(''); const share = ref<Record<string, any>>({}); const markdown = new MarkdownIt({ breaks:true,linkify:true })
onMounted(async()=>{try{const response=await fetch(`/ai-api/shares?id=${encodeURIComponent(String(route.params.id))}`);const data=await response.json();if(!response.ok)throw new Error(data.error||'分享加载失败');share.value=data.share}catch(e){error.value=e instanceof Error?e.message:'分享加载失败'}finally{loading.value=false}})
</script>
<template><main class="shared"><header><span>AI SHARED CHAT</span><h1>{{share.title||'共享会话'}}</h1><p>只读会话</p></header><div v-if="loading" class="state">正在加载...</div><div v-else-if="error" class="state error">{{error}}</div><section v-else class="messages"><article v-for="message in share.messages||[]" :key="message.id" :class="message.role"><b>{{message.role==='user'?'用户':'AI'}}</b><div v-html="markdown.render(message.content||'')"></div></article></section></main></template>
<style scoped>.shared{min-height:100vh;padding:38px 20px;background:#fff;color:#172033}.shared header,.messages{max-width:860px;margin:auto}.shared header{padding-bottom:22px;border-bottom:1px solid #e5e7eb}.shared header span{color:var(--brand-primary);font-size:10px;font-weight:700;letter-spacing:.12em}.shared h1{margin:8px 0 4px}.shared p{margin:0;color:#64748b}.messages{padding-top:28px}.messages article{display:grid;grid-template-columns:48px 1fr;gap:12px;margin-bottom:26px;line-height:1.75}.messages b{font-size:12px}.messages .user div{padding:10px 13px;border-radius:8px;background:#f1f5f9}.state{padding:80px;text-align:center;color:#64748b}.error{color:#ef4444}</style>
