import { computed, reactive } from 'vue'
import { apiGetImages, apiGetProperties, apiGetTags, apiAddTag, SERVER_PREFIX, apiAddProperty, apiAddPropertyToImage, apiUpdateTag, apiAddFolder, apiUpdateProperty, apiDeleteProperty } from '../data/api'
import { PropertyType, Tag, Tags, TagsTree, Property, GlobalStore, Properties, Images, PropsTree, ReactiveStore, PropertyValue} from '../data/models'

export const globalStore: ReactiveStore = reactive<GlobalStore>({
  images: {} as Images,
  tags: {} as Tags,
  properties: {} as Properties,
  
  imageList: computed(() => {
    return Object.keys(globalStore.images).map(sha1 => {
      return {url: SERVER_PREFIX + globalStore.images[sha1].url, imageName: sha1}
  })}),

  tagTrees: computed(() => {
    const tree:PropsTree = {}
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

  async addOrUpdatePropertyToImage(sha1: string, propertyId:number, value: any){
    const newValue:PropertyValue = await apiAddPropertyToImage(sha1, propertyId, value)
    if(!this.images[sha1].properties[propertyId]){
      this.images[sha1].properties[propertyId] = {propertyId, value}
    }
    else{
      this.images[sha1].properties[propertyId].value = newValue.value
    }
  },

  async updateTag(propId: number, tagId: number, color?:string, parentId?: number, value?: any){
    const newTag = await apiUpdateTag(tagId, color, parentId, value)
    this.tags[propId][tagId] = newTag
  },

  async addFolder(folder: string){
    apiAddFolder(folder).then(() => globalStore.fetchAllData())
  },

  async updateProperty(propertyId: number, type?: PropertyType, name?: string){
    const newProperty = await apiUpdateProperty(propertyId, type, name)
    this.properties[propertyId] = newProperty
  },

  async deleteProperty(propertyId:number){
    await apiDeleteProperty(propertyId)
    delete this.properties[propertyId]
  }

})

function getPropertyTree(property: Tags):TagsTree{
  let tree:TagsTree = {0: {children: {}, localId: '0', value: 'root', id: 0}}
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