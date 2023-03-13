import { ComputedRef } from 'vue'
import { computed, reactive } from 'vue'
import { apiGetImages, apiGetProperties, apiGetTags, apiAddTag, SERVER_PREFIX, apiAddProperty } from './utils/api'
import { PropertyType, Tag, Tags, TagsTree, Property, GlobalStore, Properties, Images, PropsTree } from './utils/models'

export const globalStore:GlobalStore = reactive({
  images: {} as Images,
  tags: {} as Tags,
  properties: {} as Properties,
  
  imageList: computed(() => {
    return Object.keys(globalStore.images).map(sha1 => {
      return {url: SERVER_PREFIX + globalStore.images[sha1].url, imageName: sha1}
  })}),

  tagTrees: computed(() => {
    const tree:any = {}
    Object.entries(globalStore.tags).forEach(([propId, tags]) => {tree[parseInt(propId)] = getPropertyTree(tags)})
    return tree 
  }),

  async fetchAllData() {
    this.images = await apiGetImages()
    this.tags = await apiGetTags()
    this.properties = await apiGetProperties()
  },

  async addTag(propertyId: number, tagValue:string, parentId?:number, color?:string): Promise<void>{
    const newTag: Tag = await apiAddTag(propertyId, tagValue, color, parentId)
    this.tags[propertyId][newTag.id] = newTag
  },

  async addProperty(name: string, type: PropertyType){
    const newProperty:Property = await apiAddProperty(name, type)
    this.properties[newProperty.id] = newProperty
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

function getPropertyTree(property: Tags):TagsTree{
  let tree:TagsTree = {0: {children: {}, localId: '0'}}
  let refs:any = {}
  refs[0] = tree[0]
  Object.values(property).forEach((tag:Tag) => {
      tag.parents.forEach(parent => {
        refs[parent].children[tag.id] = {...tag, children: {}, localId: `${refs[parent].localId}.${tag.id}`}
        refs[tag.id] = refs[parent].children[tag.id]
      })
  })
  return tree
}