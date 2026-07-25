<script setup lang="ts">
import { Hide, View } from '@element-plus/icons-vue'

withDefaults(
  defineProps<{
    displayValue: string
    showRevealButton?: boolean
    showHideButton?: boolean
    loading?: boolean
    revealText?: string
    hideText?: string
  }>(),
  {
    showRevealButton: false,
    showHideButton: false,
    loading: false,
    revealText: '验证查看',
    hideText: '再次隐藏',
  },
)

const emit = defineEmits<{
  reveal: []
  hide: []
}>()
</script>

<template>
  <div class="protected-reveal-field">
    <el-input :model-value="displayValue" readonly />

    <div v-if="showRevealButton || showHideButton" class="protected-reveal-field__actions">
      <el-button
        v-if="showRevealButton"
        type="primary"
        plain
        :icon="View"
        :loading="loading"
        @click="emit('reveal')"
      >
        {{ revealText }}
      </el-button>

      <el-button
        v-if="showHideButton"
        plain
        :icon="Hide"
        @click="emit('hide')"
      >
        {{ hideText }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.protected-reveal-field {
  display: grid;
  gap: 10px;
}

.protected-reveal-field__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
</style>
