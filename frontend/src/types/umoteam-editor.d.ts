declare module '@umoteam/editor' {
  import type { DefineComponent, Plugin } from 'vue'

  export const UmoEditor: DefineComponent<Record<string, unknown>, Record<string, unknown>, any>
  export const useUmoEditor: Plugin
}

declare module '@umoteam/editor/style'
