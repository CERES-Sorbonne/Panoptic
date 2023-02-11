import { reactive } from 'vue'

export const globalStore = reactive({
  images: [],
  prefixUrl: "https://ceres.huma-num.fr/panoptic-back"
//   filters: {},
//   order: {},
//   group: {}
})