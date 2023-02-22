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
    for(let image of globalStore.images){
      for(let tag of image.tags){
        tags[tag] = !tags[tag] ? 1 : tags[tag]++
      }
    }
    return tags
  }),
  async addTag(image, tag){
    console.log(image)
    // on remplace l'image modifiée à l'index par la nouvelle 
    this.images[this.images.findIndex(i => i.name === image.name)] = await apiAddTag(image, tag)
  },
  removeTag(image, tag){
    this.images = [apiRemoveTag(image, tag), ...this.images]
  }
//   filters: {},
//   order: {},
//   group: {}
})