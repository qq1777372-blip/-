<script setup lang="ts">
import { computed,onMounted,ref } from 'vue'
import { IonButton,IonContent,IonIcon,IonPage,alertController,toastController } from '@ionic/vue'
import { createOutline,trashOutline } from 'ionicons/icons'
import { useRoute,useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'
import { api,ApiError } from '../api';import { session } from '../session';import { amount,type CompanyExpense } from '../expenses'
const route=useRoute();const router=useRouter();const record=ref<CompanyExpense|null>(null)
const canWrite=computed(()=>['editor','superadmin'].includes(session.user?.role||''))
const load=async()=>{try{record.value=await api<CompanyExpense>(`/company-expenses/${route.params.id}`)}catch(error){const toast=await toastController.create({message:error instanceof ApiError?error.detail:'详情加载失败',duration:2200,color:'danger'});await toast.present()}}
const remove=async()=>{if(!record.value)return;const alert=await alertController.create({header:'删除记录',message:`确定删除 ${record.value.expense_no} 吗？`,buttons:['取消',{text:'删除',role:'destructive',handler:async()=>{try{await api<void>(`/company-expenses/${record.value?.id}`,{method:'DELETE'});router.back()}catch(error){const toast=await toastController.create({message:error instanceof ApiError?error.detail:'删除失败，请稍后重试',duration:2200,color:'danger'});await toast.present();return false}}}]});await alert.present()};onMounted(load)
</script>
<template><IonPage><PageHeader :title="record?.category||'记账详情'" :subtitle="record?.expense_no||'完整资料'" back /><IonContent><main v-if="record" class="page-pad expense-detail">
<section class="hero panel"><small>{{ record.expense_date }}</small><h1>{{ amount(record.amount) }}</h1><p>{{ record.description }}</p></section>
<section class="panel fields">
  <div><span>消费分类</span><b>{{ record.category }}</b></div>
  <div><span>支付账户</span><b>{{ record.payment_account }}</b></div>
  <div><span>支付方式</span><b>{{ record.payment_type==='company'?'公司支付':'员工垫付' }}</b></div>
  <div><span>费用归属</span><b>{{ record.expense_scope }}</b></div>
  <div><span>提交人</span><b>{{ record.submitter_name }}</b></div>
  <a v-if="record.attachment_url" :href="record.attachment_url" target="_blank">查看票据：{{ record.attachment_name }}</a>
</section>
<div v-if="canWrite" class="actions"><IonButton @click="router.push(`/tabs/form/company-expenses/${record.id}`)"><IonIcon slot="start" :icon="createOutline" />编辑</IonButton><IonButton fill="outline" color="danger" @click="remove"><IonIcon slot="start" :icon="trashOutline" />删除</IonButton></div>
</main></IonContent></IonPage></template>
<style scoped>.expense-detail{display:grid;gap:12px}.hero{padding:22px}.hero small,.hero p{color:var(--app-muted)}.hero h1{margin:8px 0;font-size:31px;color:#1f6fe5}.hero p{margin:0}.fields div{display:flex;justify-content:space-between;gap:15px;padding:14px 16px;border-bottom:1px solid var(--app-line)}.fields span{color:var(--app-muted);font-size:13px}.fields b{text-align:right;font-size:14px}.fields a{display:block;padding:15px;color:#1f6fe5}.actions{display:grid;grid-template-columns:2fr 1fr;gap:10px}.actions ion-button{height:48px;--border-radius:13px}</style>
