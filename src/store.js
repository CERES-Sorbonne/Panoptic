import { computed, reactive } from 'vue'
import { apiGetImages, apiGetTags, apiAddTag, apiRemoveTag, SERVER_PREFIX } from './utils/api'

export const globalStore = reactive({
  images: {},
  tags: {},
  properties: {},
  
  imageList: computed(() => Object.keys(globalStore.images).map(sha1 => {return{url: SERVER_PREFIX + globalStore.images[sha1].url, imageName: globalStore.images[sha1].name}})),
  tagTrees: computed(() => {
    const tree = {}
    Object.entries(globalStore.tags).forEach(([propId, tags]) => {tree[propId] = getPropertyTree(tags)})
    return tree
  }),

  async fetchAllData() {
    this.images = await apiGetImages()
    this.tags = await apiGetTags()
    this.properties = await apiGetProperties()
  },

  async addTag(){

  },

  async addProperty(){

  },

  async addPropertyToImage(){

  },

  async updateTag(){

  },

  async updateProperty(){

  },

  async updateImageProperty(){

  },

  async addFolder(){

  }

})

function getPropertyTree(property){
  let tree = {}
  let refs = {}
  Object.values(property).forEach(tag => {
      tag.parents.forEach(parent => {
          if(parent === 0){
              tree[tag.id] = {...tag, children: {}}
              refs[tag.id] = tree[tag.id]
          }
          else{
              refs[parent].children[tag.id] = {...tag, children: {}}
              refs[tag.id] = refs[parent].children[tag.id]
          }
      })
  })
  return tree
}