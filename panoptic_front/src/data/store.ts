import { computed, reactive } from 'vue'
import {
    apiGetImages, apiGetProperties, apiGetTags, apiAddTag, apiAddProperty, apiSetPropertyValue, apiUpdateTag, apiAddFolder,
    apiUpdateProperty, apiDeleteProperty, apiDeleteTagParent, apiGetFolders, apiImportFolder, apiGetTabs, apiUpdateTab, apiAddTab,
    apiDeleteTab, apiGetMLGroups, apiGetImportStatus, apiGetSimilarImages, SERVER_PREFIX, apiUploadPropFile
} from '../data/api'
import {
    PropertyType, Tag, Tags, TagsTree, Property, GlobalStore, Properties, Images, ReactiveStore, PropertyValue, TreeTag, IndexedTags,
    Modals, buildTabState, Folders, Folder, Tabs, Tab, ImportState, PropertyID, propertyDefault, Image
} from '../data/models'

export const globalStore: ReactiveStore = reactive<GlobalStore>({
    images: {} as Images,
    sha1Index: {} as Images,
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
        tabs.forEach((t: Tab) => {
            // old version compability
            if (t.data.selectedFolders == undefined) {
                t.data.selectedFolders = {}
            }
            if (t.data.visibleFolders == undefined) {
                t.data.visibleFolders = {}
            }
            globalStore.tabs[t.id] = t
        })

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
        return Object.keys(globalStore.images).map(Number).map(id => {
            return { url: globalStore.images[id].url, imageName: globalStore.images[id].sha1 }
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
        return Object.values(globalStore.folders).filter(f => f.parent == null) as Array<Folder>
    }),
    showModal(modalId: Modals, data: any) {
        globalStore.openModal.id = modalId
        globalStore.openModal.data = data
    },

    hideModal() {
        globalStore.openModal = { id: null, data: null }
    },
    getOneImagePerSha1(sha1s: Array<string>) {
        return sha1s.map(sha1 => globalStore.sha1Index[sha1][0])
    },
    importImage(img: Image) {
        img.properties[PropertyID.sha1] = { propertyId: PropertyID.sha1, value: img.sha1 }
        img.properties[PropertyID.ahash] = { propertyId: PropertyID.ahash, value: img.ahash }
        img.containerRatio = computeContainerRatio(img)

        if(!Array.isArray(globalStore.sha1Index[img.sha1])) {
            globalStore.sha1Index[img.sha1] = []
        }
        globalStore.sha1Index[img.sha1].push(img)
        // for(let [id, prop] of Object.entries(img.properties)){
        //     if(this.properties[parseInt(id)].type == PropertyType.date){
        //         prop.value = moment(prop.value).format()
        //     }
        // }
        globalStore.images[img.id] = img
    },
    async fetchAllData() {
        let images = await apiGetImages()
        let tags = await apiGetTags()
        let properties = await apiGetProperties()
        let folders = await apiGetFolders()
        //console.log(folders)


        properties[PropertyID.sha1] = { id: PropertyID.sha1, name: 'sha1', type: PropertyType.sha1 }
        properties[PropertyID.ahash] = { id: PropertyID.ahash, name: 'average hash', type: PropertyType.ahash }

        Object.values(images).forEach(this.importImage)


        this.tags = tags
        this.properties = properties
        this.folders = buildFolderNodes(folders)

        await this.loadTabState()


        this.importState = await apiGetImportStatus()
        setInterval(async () => { globalStore.applyImportState(await apiGetImportStatus()) }, 1000)

        this.isLoaded = true
    },
    applyImportState(state: ImportState) {
        state.new_images.forEach(img => img.url = SERVER_PREFIX + img.url)
        // console.log(state.new_images)
        state.new_images.forEach(globalStore.importImage)
        this.importState = state
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
        // also reload images since the tag should be removed from their properties
        let images = await apiGetImages()
        Object.values(images).forEach(globalStore.importImage)
        this.tags = await apiGetTags()
    },

    async addProperty(name: string, type: PropertyType) {
        const newProperty: Property = await apiAddProperty(name, type)
        this.properties[newProperty.id] = newProperty
    },

    async addOrUpdatePropertyToImage(imageIds: number | number[], propertyId: number, value: any) {
        console.log(imageIds)
        console.log(propertyId)
        console.log(value)
        let type = this.properties[propertyId].type
        if(!Array.isArray(imageIds)){
            imageIds = [imageIds]
        }
        if (value == propertyDefault(type) || Array.isArray(value) && value.length == 0) {
            value = undefined
        }
        const newValue = await apiSetPropertyValue(imageIds, propertyId, value)
        for(let id of imageIds){
            this.images[id].properties[propertyId] = newValue
        }
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
    async computeMLGroups(images: Array<string> = undefined, nbClusters: number = 10) {
        let res: [[number]]
        if (images) {
            res = await globalStore.getMLGroups(Math.min(nbClusters, images.length), images)
        }
        else {
            res = await globalStore.getMLGroups(nbClusters)
        }
        return res
    },

    async getSimilarImages(sha1: string | string[]) {
        sha1 = Array.isArray(sha1) ? sha1 : [sha1]
        const res = await apiGetSimilarImages(sha1)
        return res
    },
    getFolderChildren(folderId: number) {
        let res = {} as { [key: number]: boolean }
        let children = this.folders[folderId].children
        children.forEach(c => {
            res[c.id] = true
            let subRes = globalStore.getFolderChildren(c.id)
            subRes.forEach((r: any) => res[r] = true)
        })
        return Object.keys(res).map(Number)
    },

    async uploadPropFile(file: any) {
        apiUploadPropFile(file)
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

function buildFolderNodes(folders: Array<Folder>) {
    let res = {} as Folders
    folders.forEach(f => {
        f.children = []
        res[f.id] = f
    })

    let parentMap = {} as { [key: number]: Array<Folder> }
    folders.forEach(f => {
        if (!f.parent) {
            return
        }
        if (parentMap[f.parent] == undefined) {
            parentMap[f.parent] = []
        }
        parentMap[f.parent].push(f)
    })
    Object.keys(parentMap).forEach((parentId: any) => {
        if (parentId == undefined) {
            return
        }
        parentMap[parentId].forEach(f => {
            res[parentId].children.push(f)
        })
    })
    return res
}

function computeContainerRatio(img: Image) {
    let ratio = img.width / img.height
    return Math.max(Math.min(2, ratio), 1)
}