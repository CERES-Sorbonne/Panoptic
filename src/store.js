import { computed, reactive } from 'vue'
import { apiGetImages, apiAddTag, apiRemoveTag, SERVER_PREFIX } from './utils/api'

export const globalStore = reactive({
  images: [],
  async fetchImages() {
    this.images = await apiGetImages()
    this.images = this.images[0].map(el => ({url: SERVER_PREFIX + el.name, tags:[], ...el}))
  },
  tags: computed(() => {
    let tags = {}
    for(let image of this.images){
      for(let tag of image.tags){
        tags[tag] = tags[tag] ? 1 : tags[tag]++
      }
    }
    return tags
  }),
  addTag(image, tag){
    this.images = [...apiAddTag(image, tag), ...this.images]
  },
  removeTag(image, tag){
    this.images = [...apiRemoveTag(image, tag), ...this.images]
  }
//   filters: {},
//   order: {},
//   group: {}
})