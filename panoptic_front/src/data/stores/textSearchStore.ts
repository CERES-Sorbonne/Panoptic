import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSearchStore = defineStore('search', () => {
  const isLoading = ref(false)

  function setLoading(loading: boolean) {
    isLoading.value = loading
  }

  return {
    isLoading,
    setLoading
  }
})