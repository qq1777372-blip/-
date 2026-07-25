<script setup lang="ts">
import { Delete, RefreshLeft, UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadInstance, UploadRawFile } from 'element-plus'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { deleteCurrentUserAvatar, updateCurrentUserProfile, uploadCurrentUserAvatar } from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const authStore = useAuthStore()
const loading = ref(false)
const uploadRef = ref<UploadInstance>()
const uploadFileList = ref<UploadFile[]>([])
const selectedAvatarFile = ref<File | null>(null)
const currentAvatarUrl = ref('')
const avatarPreviewUrl = ref('')
const removeAvatar = ref(false)

const form = reactive({
  username: '',
  displayName: '',
})

let objectPreviewUrl: string | null = null

const hasCurrentAvatar = computed(() => Boolean(currentAvatarUrl.value))
const hasPendingRemoval = computed(() => removeAvatar.value && !selectedAvatarFile.value)

function getErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.message ?? fallback)
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return fallback
}

function closeDialog() {
  emit('update:modelValue', false)
}

function releasePreviewUrl() {
  if (objectPreviewUrl) {
    URL.revokeObjectURL(objectPreviewUrl)
    objectPreviewUrl = null
  }
}

function setExistingPreview(url: string | null) {
  releasePreviewUrl()
  currentAvatarUrl.value = url ?? ''
  avatarPreviewUrl.value = removeAvatar.value ? '' : currentAvatarUrl.value
}

function setFilePreview(file: File) {
  releasePreviewUrl()
  objectPreviewUrl = URL.createObjectURL(file)
  avatarPreviewUrl.value = objectPreviewUrl
}

function resetForm() {
  const currentUser = authStore.currentUser
  form.username = currentUser?.username ?? ''
  form.displayName = currentUser?.display_name ?? ''
  selectedAvatarFile.value = null
  uploadFileList.value = []
  removeAvatar.value = false
  setExistingPreview(currentUser?.avatar_url ?? null)
  uploadRef.value?.clearFiles()
}

function validateAvatarFile(file: Pick<File, 'type' | 'size'>) {
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp']
  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('仅支持 JPG、PNG、WebP 图片')
    return false
  }

  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('头像大小不能超过 5MB')
    return false
  }

  return true
}

function beforeAvatarUpload(rawFile: UploadRawFile) {
  return validateAvatarFile(rawFile)
}

function handleUploadChange(uploadFile: UploadFile, fileList: UploadFile[]) {
  const rawFile = uploadFile.raw
  if (!rawFile) {
    return
  }

  if (!validateAvatarFile(rawFile)) {
    uploadFileList.value = []
    return
  }

  removeAvatar.value = false
  selectedAvatarFile.value = rawFile
  uploadFileList.value = fileList.slice(-1)
  setFilePreview(rawFile)
}

function handleUploadRemove() {
  selectedAvatarFile.value = null
  uploadFileList.value = []

  if (removeAvatar.value || !currentAvatarUrl.value) {
    releasePreviewUrl()
    avatarPreviewUrl.value = ''
    return
  }

  setExistingPreview(currentAvatarUrl.value)
}

function markAvatarForRemoval() {
  selectedAvatarFile.value = null
  uploadFileList.value = []
  removeAvatar.value = true
  uploadRef.value?.clearFiles()
  releasePreviewUrl()
  avatarPreviewUrl.value = ''
}

function restoreCurrentAvatar() {
  selectedAvatarFile.value = null
  uploadFileList.value = []
  removeAvatar.value = false
  uploadRef.value?.clearFiles()
  setExistingPreview(currentAvatarUrl.value || null)
}

async function submit() {
  if (!form.username.trim()) {
    ElMessage.warning('登录账号不能为空')
    return
  }

  loading.value = true
  try {
    let currentUser = await updateCurrentUserProfile({
      username: form.username.trim(),
      display_name: form.displayName.trim() || null,
    })

    if (selectedAvatarFile.value) {
      currentUser = await uploadCurrentUserAvatar(selectedAvatarFile.value)
    } else if (hasPendingRemoval.value && hasCurrentAvatar.value) {
      currentUser = await deleteCurrentUserAvatar()
    }

    authStore.currentUser = currentUser
    ElMessage.success('账号资料已更新')
    closeDialog()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '更新账号资料失败'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      resetForm()
      return
    }

    releasePreviewUrl()
  },
)

onBeforeUnmount(() => {
  releasePreviewUrl()
})
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="账号资料"
    width="620px"
    destroy-on-close
    @close="closeDialog"
  >
    <el-form label-position="top">
      <el-form-item label="登录账号" required>
        <el-input v-model="form.username" placeholder="请输入登录账号" />
      </el-form-item>

      <el-form-item label="用户姓名">
        <el-input v-model="form.displayName" placeholder="可选，用于页面展示名称" />
      </el-form-item>

      <el-form-item label="头像">
        <div class="profile-avatar-panel">
          <div class="profile-avatar-preview">
            <img v-if="avatarPreviewUrl" :src="avatarPreviewUrl" alt="头像预览" />
            <span v-else>{{ (form.displayName || form.username || '?').slice(0, 1).toUpperCase() }}</span>
          </div>

          <div class="profile-avatar-actions">
            <el-upload
              ref="uploadRef"
              v-model:file-list="uploadFileList"
              action="#"
              :auto-upload="false"
              :show-file-list="true"
              :limit="1"
              accept="image/jpeg,image/png,image/webp"
              :before-upload="beforeAvatarUpload"
              :on-change="handleUploadChange"
              :on-remove="handleUploadRemove"
            >
              <el-button type="primary" plain :icon="UploadFilled">选择头像</el-button>
            </el-upload>

            <div class="profile-avatar-inline-actions">
              <el-button
                v-if="hasCurrentAvatar && !hasPendingRemoval && !selectedAvatarFile"
                text
                type="danger"
                :icon="Delete"
                @click="markAvatarForRemoval"
              >
                删除当前头像
              </el-button>

              <el-button
                v-if="hasPendingRemoval"
                text
                :icon="RefreshLeft"
                @click="restoreCurrentAvatar"
              >
                恢复当前头像
              </el-button>
            </div>

            <div class="section-desc">
              支持 JPG / PNG / WebP，头像大小不超过 5MB。保存后才会生效。
            </div>
          </div>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="closeDialog">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">保存资料</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.profile-avatar-panel {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  width: 100%;
}

.profile-avatar-preview {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 104px;
  height: 104px;
  overflow: hidden;
  border: 1px solid #dbe4f0;
  border-radius: 24px;
  background: linear-gradient(135deg, #1677ff, #36cfc9);
  color: #ffffff;
  font-size: 34px;
  font-weight: 800;
}

.profile-avatar-preview img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  background: #f8fafc;
}

.profile-avatar-actions {
  display: grid;
  gap: 8px;
  min-width: 0;
  flex: 1 1 auto;
}

.profile-avatar-inline-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 640px) {
  .profile-avatar-panel {
    flex-direction: column;
  }
}
</style>
