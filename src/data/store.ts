import { computed, reactive } from 'vue'
import { apiGetImages, apiGetProperties, apiGetTags, apiAddTag, apiAddProperty, apiAddPropertyToImage, apiUpdateTag, apiAddFolder, apiUpdateProperty, apiDeleteProperty, apiDeleteTagParent, apiGetFolders, apiImportFolder } from '../data/api'
import { PropertyType, Tag, Tags, TagsTree, Property, GlobalStore, Properties, Images, ReactiveStore, PropertyValue, TreeTag, IndexedTags, Modals, FilterOperator, TabState } from '../data/models'

export const globalStore: ReactiveStore = reactive<GlobalStore>({
    images: {} as Images,
    tags: {} as Tags,
    properties: {} as Properties,
    folders: [] as Array<string>,
    tabs: [] as Array<TabState>,
    settings: {
        pageSize: 200,
        propertyTypes: Object.values(PropertyType),
        propertySettings: {}
    },
    openModal: { id: null, data: null },

    selectedTabName: '',
    addTab(tabName: string) {
        globalStore.tabs.push({
            name: tabName,
            filter: { depth: 0, filters: [], groupOperator: FilterOperator.and, isGroup: true },
            display: 'grid',
            groups: [{ name: 'all', images: 34 }],
        })
        globalStore.saveTabState()
    },
    removeTab(tabName: string) {
        let index = globalStore.tabs.findIndex(t => t.name == tabName)
        if (index < 0) {
            return
        }
        globalStore.tabs.splice(index, 1)
        globalStore.saveTabState()
    },
    selectTab(tabName: string) {
        globalStore.selectedTabName = tabName
        globalStore.saveTabState()
    },
    saveTabState() {
        localStorage.setItem('tabs', JSON.stringify(globalStore.tabs))
        localStorage.setItem('selectedTabName', this.selectedTabName)
    },
    loadTabState() {
        try {
            let tabs = JSON.parse(localStorage.getItem('tabs'))
            let selectedTabName = localStorage.getItem('selectedTabName')
            if (tabs) {
                this.tabs = tabs
                console.log(globalStore.tabs)
            }
            if (selectedTabName) {
                globalStore.selectTab(selectedTabName)
            }
        }
        catch(e: any) {
            throw e
        }
    },

    imageList: computed(() => {
        return Object.keys(globalStore.images).map(sha1 => {
            return { url: globalStore.images[sha1].url, imageName: sha1 }
        })
    }),

    propertyList: computed(() => {
        return Object.values(globalStore.properties) as Array<Property>
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

    showModal(modalId: Modals, data: any) {
        globalStore.openModal.id = modalId
        globalStore.openModal.data = data
    },

    hideModal() {
        globalStore.openModal = { id: null, data: null }
    },

    async fetchAllData() {
        let images = await apiGetImages()
        let tags = await apiGetTags()
        let properties = await apiGetProperties()
        let folders = await apiGetFolders()

        this.images = images
        this.tags = tags
        this.properties = properties
        this.folders = folders

        this.loadTabState()
    },

    async importFolders() {
        await apiImportFolder()
        await this.fetchAllData()
    },

    async addTag(propertyId: number, tagValue: string, parentId?: number, color?: string): Promise<Tag> {
        const newTag: Tag = await apiAddTag(propertyId, tagValue, color, parentId)
        this.tags[propertyId][newTag.id] = newTag
        return newTag
    },

    async deleteTagParent(propertyId: number, tagId: number, parent_id: number) {
        const deletedIds: number[] = await apiDeleteTagParent(tagId, parent_id)
        this.tags = await apiGetTags()
        // also reload images since the tag should be removed from their properties
        this.images = await apiGetImages()
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