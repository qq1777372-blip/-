import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const viewportWidth = ref(typeof window === 'undefined' ? 1440 : window.innerWidth)
const viewportHeight = ref(typeof window === 'undefined' ? 900 : window.innerHeight)

function updateViewportSize() {
  viewportWidth.value = window.innerWidth
  viewportHeight.value = window.innerHeight
}

export function useViewport() {
  onMounted(() => {
    updateViewportSize()
    window.addEventListener('resize', updateViewportSize)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', updateViewportSize)
  })

  const isTablet = computed(() => viewportWidth.value <= 992)
  const isMobile = computed(() => viewportWidth.value <= 768)

  return {
    viewportWidth,
    viewportHeight,
    isTablet,
    isMobile,
  }
}
