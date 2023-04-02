import { computed, reactive } from 'vue'
import { apiGetImages, apiGetProperties, apiGetTags, apiAddTag, SERVER_PREFIX, apiAddProperty, apiAddPropertyToImage, apiUpdateTag, apiAddFolder, apiUpdateProperty, apiDeleteProperty, apiDeleteTagParent, apiGetParams, apiImportFolder } from '../data/api'
import { PropertyType, Tag, Tags, TagsTree, Property, GlobalStore, Properties, Images, PropsTree, ReactiveStore, PropertyValue, TreeTag, Params, IndexedTags } from '../data/models'

export const globalStore: ReactiveStore = reactive<GlobalStore>({
    images: {} as Images,
    tags: {} as Tags,
    properties: {} as Properties,
    params: {} as Params,
    settings: {pageSize: 200, propertyTypes: Object.values(PropertyType)},

    imageList: computed(() => {
        return Object.keys(globalStore.images).map(sha1 => {
            return { url: SERVER_PREFIX + globalStore.images[sha1].url, imageName: sha1 }
        })
    }),

    propertyList: computed(() => {
        return Object.values(globalStore.properties)
    }),

    tagTrees: computed(() => {
        const tree: TagsTree = {}
        Object.values(globalStore.properties).forEach((property: Property) => {
            if (!globalStore.tags[property.id]) {
                globalStore.tags[property.id] = {}
            }
            tree[property.id] = getPropertyTree(globalStore.tags[property.id])
        })
        return tree
    }),

    async fetchAllData() {
        this.images = await apiGetImages()
        this.tags = await apiGetTags()
        this.properties = await apiGetProperties()
        this.params = await apiGetParams()
        // for (let sha1 in this.images) {
        //     for (let propId in this.properties) {
        //         if (!this.images[sha1].properties[propId]) {
        //             this.images[sha1].properties[propId] = { propertyId: Number(propId), value: undefined, type: this.properties[propId].type }
        //         }
        //         else {
        //             this.images[sha1].properties[propId].type = this.properties[propId].type
        //         }
        //     }
        // }
    },

    async importFolders() {
        await apiImportFolder()
        await this.fetchAllData()
    },

    async addTag(propertyId: number, tagValue: string, parentId?: number, color?: string): Promise<void> {
        const newTag: Tag = await apiAddTag(propertyId, tagValue, color, parentId)
        this.tags[propertyId][newTag.id] = newTag
    },

    async deleteTagParent(propertyId: number, tagId: number, parent_id: number) {
        const deletedIds: number[] = await apiDeleteTagParent(tagId, parent_id)
        this.tags = await apiGetTags()
    },

    async addProperty(name: string, type: PropertyType) {
        const newProperty: Property = await apiAddProperty(name, type)
        this.properties[newProperty.id] = newProperty
    },

    async addOrUpdatePropertyToImage(sha1: string, propertyId: number, value: any) {
        const newValue: PropertyValue = await apiAddPropertyToImage(sha1, propertyId, value)
        this.images[sha1].properties[propertyId] = newValue
    },

    async updateTag(propId: number, tagId: number, color?: string, parentId?: number, value?: any) {
        const newTag = await apiUpdateTag(tagId, color, parentId, value)
        this.tags[propId][tagId] = newTag
    },

    async addFolder(folder: string) {
        apiAddFolder(folder).then(() => globalStore.fetchAllData())
    },

    async updateProperty(propertyId: number, type?: PropertyType, name?: string) {
        const newProperty = await apiUpdateProperty(propertyId, type, name)
        this.properties[propertyId] = newProperty
    },

    async deleteProperty(propertyId: number) {
        await apiDeleteProperty(propertyId)
        delete this.properties[propertyId]
    }

})


function getPropertyTree(tags: IndexedTags): TreeTag {
    let children: any = {}

    // get tagId to children list mapping
    Object.values(tags).forEach(tag => {
        tag.parents.forEach((p: number) => {
            if (!children[p]) {
                children[p] = []
            }
            children[p].push(tag.id)
        })
    })

    // create a root node to make tree visiting more straightforward
    let root = { id: 0, localId: '0', value: 'root' }
    let nodes = [root, ...Object.values(tags)]

    // fill children property in each node
    nodes = nodes.map((n: TreeTag) => {
        return { ...n, children: children[n.id] }
    })
    let nodeIndex: any = {}
    nodes.forEach(n => nodeIndex[n.id] = n)

    root = nodeIndex['0']

    // recursive function. builds all possible path starting from a rootNode
    let buildTree = (rootNode: any, parent?: any) => {
        if (parent == undefined) {
            rootNode.localId = rootNode.id + ''
        } else {
            rootNode.localId = parent.localId + '.' + rootNode.id
            rootNode.localParent = parent.id
        }
        if (rootNode.children) {
            rootNode.children = rootNode.children.map((childId: number) => {
                let child = { ...nodeIndex[childId] }
                return buildTree(child, rootNode)
            })
        }
        return rootNode
    }

    return buildTree(root)
}