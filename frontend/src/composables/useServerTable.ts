import { computed, ref, watch, type Ref } from 'vue'

export type SortOrder = 'asc' | 'desc'

export interface ServerTableOptions {
  defaultPageSize?: number
  defaultSortBy?: string
  defaultSortOrder?: SortOrder
}

export function useServerTable(keyword: Ref<string>, options: ServerTableOptions = {}) {
  const page = ref(1)
  const pageSize = ref(options.defaultPageSize ?? 20)
  const sortBy = ref(options.defaultSortBy ?? 'id')
  const sortOrder = ref<SortOrder>(options.defaultSortOrder ?? 'desc')

  const query = computed(() => ({
    page: page.value,
    page_size: pageSize.value,
    keyword: keyword.value.trim() || undefined,
    sort_by: sortBy.value,
    sort_order: sortOrder.value,
  }))

  function setSort(field: string, order: 'ascending' | 'descending' | null) {
    if (!order) return
    sortBy.value = field
    sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
    page.value = 1
  }

  function reset() {
    page.value = 1
    pageSize.value = options.defaultPageSize ?? 20
    sortBy.value = options.defaultSortBy ?? 'id'
    sortOrder.value = options.defaultSortOrder ?? 'desc'
  }

  watch(keyword, () => {
    page.value = 1
  })

  return { page, pageSize, sortBy, sortOrder, query, setSort, reset }
}
