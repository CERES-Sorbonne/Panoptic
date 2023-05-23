import { computed, reactive } from 'vue'
import { apiGetImages, apiGetProperties, apiGetTags, apiAddTag, apiAddProperty, apiAddPropertyToImage, apiUpdateTag, apiAddFolder, apiUpdateProperty, apiDeleteProperty, apiDeleteTagParent, apiGetFolders, apiImportFolder, apiGetTabs, apiUpdateTab, apiAddTab, apiDeleteTab, apiGetMLGroups, apiGetImportStatus } from '../data/api'
import { PropertyType, Tag, Tags, TagsTree, Property, GlobalStore, Properties, Images, ReactiveStore, PropertyValue, TreeTag, IndexedTags, Modals, FilterOperator, TabState, buildTabState, Folders, Folder, Tabs, Tab, ImportState, PropertyID, Image } from '../data/models'

export const globalStore: ReactiveStore = reactive<GlobalStore>({
    images: {} as Images,
    tags: {} as Tags,
    tagNodes: {} as Tags,
    properties: {} as Properties,
    folders: {} as Folders,
    tabs: {} as Tabs,
    importState: {} as ImportState,
    settings: {
        pageSize: 200,
        propertyTypes: Object.values(PropertyType),
        propertySettings: {}
    },
    openModal: { id: null, data: null },
    isLoaded: false,

    selectedTab: 0,
    async addTab(tabName: string) {
        let state = buildTabState()
        let tab = await apiAddTab({ name: tabName, data: state })
        this.tabs[tab.id] = tab
        this.selectedTab = tab.id
    },
    async removeTab(tabId: number) {
        await apiDeleteTab(tabId)
        delete this.tabs[tabId]
        this.verifySelectedTab()
    },
    async updateTab(tab: Tab) {
        await apiUpdateTab(tab)
    },
    selectTab(tabName: string) {
        globalStore.selectedTabName = tabName
        globalStore.saveTabState()
    },
    async loadTabState() {
        let tabs = await apiGetTabs()
        // console.log(tabs)
        tabs.forEach((t: Tab) => globalStore.tabs[t.id] = t)

        if (tabs.length == 0) {
            await this.addTab('Tab1')
        }

        this.verifySelectedTab()
    },
    verifySelectedTab() {
        if (this.tabs[this.selectedTab] != undefined) {
            return
        }
        this.selectedTab = Object.keys(this.tabs)[0]
    },
    imageList: computed(() => {
        return Object.keys(globalStore.images).map(sha1 => {
            return { url: globalStore.images[sha1].url, imageName: sha1 }
        })
    }),

    propertyList: computed(() => {
        return Object.values(globalStore.properties) as Array<Property>
    }),
    setPropertyVisible(propId: number, value: boolean) {
        this.tabs[this.selectedTab].data.visibleProperties[propId] = value
    },
    getPropertyVisible(propId: number) {
        //console.log(this.tabs[this.selectedTab])
        return this.tabs[this.selectedTab].data.visibleProperties[propId]
    },
    tagTrees: computed(() => {
        const tree: TagsTree = {}
        Object.values(globalStore.properties).forEach((property: Property) => {
            if (!globalStore.tags[property.id]) {
                globalStore.tags[property.id] = {}
            }
            tree[property.id] = getPropertyTree(globalStore.tags[property.id], property.id)
        })
        return tree
    }),
    // tagsWithChildren: computed(() => {
    //     let res = {} as Tags

    // }),
    folderTree: computed(() => {
        let copies = {} as Folders
        for (let k in globalStore.folders) {
            copies[k] = { ...globalStore.folders[k] }
            copies[k].children = []
        }
        for (let k in copies) {
            let parent = copies[k].parent
            if (parent != undefined) {
                copies[parent].children.push(copies[k])

            }
        }
        return Object.values(copies).filter(f => f.parent == undefined) as Array<Folder>
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
        //console.log(folders)

        Object.values(images).forEach(img => {
            img.properties[PropertyID.sha1] = { propertyId: PropertyID.sha1, value: img.sha1 }
            img.properties[PropertyID.ahash] = { propertyId: PropertyID.ahash, value: img.ahash }
        })
        properties[PropertyID.sha1] = { id: PropertyID.sha1, name: 'sha1', type: PropertyType.sha1 }
        properties[PropertyID.ahash] = { id: PropertyID.ahash, name: 'average hash', type: PropertyType.ahash }

        this.images = images
        this.tags = tags
        this.properties = properties
        this.folders = {}
        folders.forEach((f: Folder) => this.folders[f.id] = f)

        await this.loadTabState()


        this.importState = await apiGetImportStatus()
        setInterval(async () => { this.importState = await apiGetImportStatus() }, 1000)
        console.log(this.importState)

        this.isLoaded = true
    },

    async importFolders() {
        await apiImportFolder()
        await this.fetchAllData()
    },

    async addTag(propertyId: number, tagValue: string, parentId?: number, color?: string): Promise<Tag> {
        //console.log(color)
        if (color == undefined) {
            //console.log("find color")
            let options = ["7c1314", "c31d20", "f94144", "f3722c", "f8961e", "f9c74f", "90be6d", "43aa8b", "577590", "9daebe"]
            let r = Math.round(Math.random() * (options.length - 1))
            color = '#' + options[r]
        }
        const newTag: Tag = await apiAddTag(propertyId, tagValue, color, parentId)
        this.tags[propertyId][newTag.id] = newTag
        return newTag
    },

    async deleteTagParent(tagId: number, parent_id: number) {
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
    },

    async getMLGroups(nbGroups: number = 50, imageList: string[] = []) {
        const res = await apiGetMLGroups(nbGroups, imageList)
        return res
    },
    async computeMLGroups(images: Array<Image> = undefined, nbClusters: number = 10){
        let sha1List: [[string]]
        if(images){
            sha1List = await globalStore.getMLGroups(Math.min(nbClusters, images.length), images)
        }
        else{
            sha1List = await globalStore.getMLGroups(nbClusters)
        }
        const ml_groups = sha1List.map(group => group.map(sha1 => globalStore.images[sha1]))
        return ml_groups
    }

})


function getPropertyTree(tags: IndexedTags, propId: number): TreeTag {
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
    let nodeIndex = {} as any
    nodes.forEach(n => nodeIndex[n.id] = n)

    root = nodeIndex['0']


    let tagNodes = {} as { [key: string]: Tag }


    // recursive function. builds all possible path starting from a rootNode
    let buildTree = (rootNode: any, parent?: any) => {
        if (parent == undefined) {
            rootNode.localId = rootNode.id + ''
        } else {
            tagNodes[rootNode.id] = rootNode
            rootNode.localId = parent.localId + '.' + rootNode.id
            rootNode.localParent = parent.id
        }
        if (rootNode.children) {
            rootNode.children = rootNode.children.map((childId: number) => {
                let child = { ...nodeIndex[childId] }
                if (rootNode.color) {
                    child.color = rootNode.color
                }
                return buildTree(child, rootNode)
            })
        }
        return rootNode
    }
    let res = buildTree(root)
    globalStore.tagNodes[propId] = tagNodes
    return res
}

// for(let [index, group] of ml_groups.entries()){
    //     let realGroup: Group = {
    //         name: 'cluster ' + index.toString(),
    //         images: group,
    //         count:group.length,
    //         groups: []
    //     }
    //     if(groupId){
    //         imageGroups[groupId].groups.push(realGroup)
    //     }
    //     else{
    //         imageGroups.push(realGroup)
    //     }
    // }