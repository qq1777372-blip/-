<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import RecordManagerPage from "./RecordManagerPage.vue";

const route = useRoute();
const detailId = computed(() => Number(route.params.id));
</script>

<template>
  <RecordManagerPage :detail-id="detailId" />
</template>
