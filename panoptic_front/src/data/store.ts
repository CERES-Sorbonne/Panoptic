/**
 * Main Store for Panoptic
 * Keeps all the raw data loaded from the Backend as a global truth
 * Main interface to modify data
 */

import { defineStore } from "pinia";
import { computed, reactive } from "vue";
import { Colors, Folder, FolderIndex, Image, ImageIndex, ImportState, ModalId, Property, PropertyID, PropertyIndex, PropertyMode, PropertyType, Sha1ToImages, TabIndex, TabState, Tag, TagIndex } from "./models";
import { buildTabState, defaultPropertyOption, objValues, propertyDefault } from "./builder";
import { apiAddFolder, apiAddProperty, apiAddTab, apiAddTag, apiAddTagParent, apiDeleteProperty, apiDeleteTab, apiDeleteTagParent, apiGetFolders, apiGetImages, apiGetImportStatus, apiGetProperties, apiGetTabs, apiGetTags, apiSetPropertyValue, apiUpdateProperty, apiUpdateTab, apiUpdateTag, apiUploadPropFile } from "./api";
import { buildFolderNodes, computeContainerRatio, computeTagCount, countImagePerFolder } from "./storeutils";
import { TabManager } from "@/core/TabManager";

let tabManager: TabManager = undefined

export const useStore = defineStore('store', () => {
    const data = reactive({
        images: {} as ImageIndex,
        sha1Index: {} as Sha1ToImages,
        properties: {} as PropertyIndex,
        tabs: {} as TabIndex,
        selectedTabId: undefined as number,
        folders: {} as FolderIndex,
    })

    const status = reactive({
        loaded: false,
        changed: false,
        renderNb: 0,
        import: {} as ImportState
    })

    const openModal = reactive({ id: undefined, data: undefined })

    // =======================
    // =======Computed=======
    // =======================

    const propertyList = computed(() => Object.values(data.properties) as Property[])
    const imageList = computed(() => Object.values(data.images) as Image[])
    const folderRoots = computed(() => {
        return Object.values(data.folders).filter(f => f.parent == null) as Folder[]
    })

    // =======================
    // =======Functions=======
    // =======================

    async function init() {
        if (!tabManager) {
            tabManager = new TabManager(getTab())
        }
        let images = await apiGetImages()
        let tags = await apiGetTags()
        let properties = await apiGetProperties()
        let folders = await apiGetFolders()

        properties[PropertyID.sha1] = { id: PropertyID.sha1, name: 'sha1', type: PropertyType._sha1, mode: 'sha1' }
        properties[PropertyID.ahash] = { id: PropertyID.ahash, name: 'average hash', type: PropertyType._ahash, mode: 'sha1' }
        properties[PropertyID.folders] = { id: PropertyID.folders, name: 'folders', type: PropertyType._folders, mode: 'sha1' }


        objValues(images).forEach((i) => importImage(i))
        data.properties = properties

        importTags(tags)

        data.folders = buildFolderNodes(folders)

        // console.time('tab state')
        await loadTabs()
        // console.timeEnd('tab state')

        status.import = await apiGetImportStatus()
        setInterval(async () => { applyImportState(await apiGetImportStatus()) }, 1000)

        updatePropertyOptions()

        computeTagCount(imageList.value, properties)

        countImagePerFolder(data.folders, imageList.value)
        verifySelectedTab()
        verifyData()

        status.loaded = true
    }

    function verifyData() {
        tabManager.verifyState()
    }

    function applyImportState(state: ImportState) {
        status.import = state
        if (!state.done) {
            status.changed = true
        }
        if (state.done && status.changed) {
            status.changed = false
            init()
        }
    }

    function getTab() {
        return data.tabs[data.selectedTabId]
    }

    async function addTab(tabName: string) {
        let state = buildTabState()
        state.name = tabName
        let tab = await apiAddTab({ data: state })
        tab.data.id = tab.id
        data.tabs[tab.id] = tab.data
        selectTab(tab.id)
    }

    async function removeTab(tabId: number) {
        await apiDeleteTab(tabId)
        delete data.tabs[tabId]
        if (objValues(data.tabs).length == 0) {
            await addTab('Tab1')
        }
        verifySelectedTab()
    }

    async function updateTab(tab: TabState) {
        await apiUpdateTab({ id: tab.id, data: tab })
    }

    function selectTab(tabId: number) {
        data.selectedTabId = tabId
        tabManager.load(getTab())
    }

    async function loadTabs() {
        let tabs = await apiGetTabs()
        tabs.forEach(t => data.tabs[t.id] = t.data)

        if (tabs.length == 0) {
            await addTab('Tab1')
        } else {
            selectTab(tabs[0].id)
        }
        verifySelectedTab()
    }

    function verifySelectedTab() {
        if (getTab() != undefined) {
            return
        }
        data.selectedTabId = Number(Object.keys(data.tabs)[0])
    }

    function showModal(modalId: ModalId, data: any) {
        openModal.id = modalId
        openModal.data = data
    }

    function hideModal() {
        Object.assign(openModal, { id: undefined, data: undefined })
    }

    function importImage(img: Image) {
        Object.keys(img.properties).forEach(pId => img.properties[pId] = Object.assign({ propertyId: Number(pId) }, img.properties[pId]))
        img.properties[PropertyID.sha1] = { propertyId: PropertyID.sha1, value: img.sha1 }
        img.properties[PropertyID.ahash] = { propertyId: PropertyID.ahash, value: img.ahash }
        img.properties[PropertyID.folders] = { propertyId: PropertyID.folders, value: img.folder_id }

        img.containerRatio = computeContainerRatio(img)

        if (!data.images[img.id]) {
            if (!Array.isArray(data.sha1Index[img.sha1])) {
                data.sha1Index[img.sha1] = []
            }
            data.sha1Index[img.sha1].push(img)
        }
        // TODO: verify it doesnt break link with the sha1Index
        data.images[img.id] = img
    }

    async function addTag(propertyId: number, tagValue: string, parentId?: number, color?: number): Promise<Tag> {
        if (color == undefined) {
            let r = Math.round(Math.random() * (Colors.length - 1))
            color = r
        }
        const newTag: Tag = await apiAddTag(propertyId, tagValue, color, parentId)
        newTag.count = 0
        if (!data.properties[propertyId].tags) {
            data.properties[propertyId].tags = {}
        }
        data.properties[propertyId].tags[newTag.id] = newTag
        return newTag
    }

    async function addTagParent(tagId: number, parentId: number) {
        const tag = await apiAddTagParent(tagId, parentId) as Tag
        Object.assign(data.properties[tag.property_id].tags[tag.id], tag)
    }

    async function deleteTagParent(tagId: number, parent_id: number, dontAsk?: boolean) {
        if (!dontAsk) {
            let ok = confirm('Delete tag: ' + tagId)
            if (!ok) return
        }
        const deletedIds: number[] = await apiDeleteTagParent(tagId, parent_id)
        // also reload images since the tag should be removed from their properties
        const tags = await apiGetTags()
        const images = await apiGetImages()
        Object.values(images).forEach(i => importImage(i))
        importTags(tags)

    }

    function importTags(tagPropIndex) {
        for (let propertyId of Object.keys(tagPropIndex).map(Number)) {
            const tags = tagPropIndex[propertyId] as TagIndex
            const property = data.properties[propertyId]
            if (!property) continue

            property.tags = tags
        }
        computeTagCount(imageList.value, data.properties)
    }

    async function addProperty(name: string, type: PropertyType, mode: PropertyMode) {
        const newProperty: Property = await apiAddProperty(name, type, mode)
        data.properties[newProperty.id] = newProperty
        updatePropertyOptions()
        getTab().visibleProperties[newProperty.id] = true
    }

    // TODO make a version that does not trigger actualisation
    async function setPropertyValue(propertyId: number, images: Image[] | Image, value: any, mode: string = null, dontEmit?: boolean) {
        if (!Array.isArray(images)) {
            images = [images]
        }

        let prop = data.properties[propertyId]

        let imageIds = undefined
        let sha1s = undefined

        if (prop.mode == PropertyMode.id) {
            imageIds = Array.from(new Set(images.map(i => i.id)))
        }
        if (prop.mode == PropertyMode.sha1) {
            sha1s = Array.from(new Set(images.map(i => i.sha1)))
        }

        let type = prop.type
        if (value == propertyDefault(type) || Array.isArray(value) && value.length == 0 || value == null) {
            value = undefined
        }
        // console.log(propertyId, imageIds, sha1s, value, prop.mode)
        const update = await apiSetPropertyValue(propertyId, imageIds, sha1s, value, mode)
        const updatedIds = update.updated_ids
        value = update.value

        for (let id of updatedIds) {
            if (mode == null) {
                data.images[id].properties[propertyId] = { propertyId, value }
            }
            else {
                let old = data.images[id].properties[propertyId] ?? { propertyId: propertyId, value: [] }
                if (!Array.isArray(old.value)) {
                    old.value = []
                }
                old.value.push(...value)
                old.value = [...new Set(old.value)]
                // console.log(data.images[id].properties[propertyId], old)
                data.images[id].properties[propertyId] = old
            }

        }

        if (data.properties[propertyId].tags != undefined) {
            computeTagCount(imageList.value, data.properties)
        }

        if (!dontEmit) tabManager.collection.update()
    }

    async function updateTag(propId: number, tagId: number, color?: number, parentId?: number, value?: any) {
        const newTag = await apiUpdateTag(tagId, color, parentId, value)
        Object.assign(data.properties[newTag.property_id].tags[newTag.id], newTag)
    }

    async function addFolder(folder: string) {
        await apiAddFolder(folder)
        init()
    }

    async function updateProperty(propertyId: number, name?: string) {
        await apiUpdateProperty(propertyId, name)
        data.properties[propertyId].name = name
        updatePropertyOptions()
    }

    async function deleteProperty(propertyId: number) {
        await apiDeleteProperty(propertyId)
        delete data.properties[propertyId]

        Object.values(data.tabs).forEach((t: TabState) => {
            Object.keys(t.visibleProperties).map(Number).forEach(k => {
                if (data.properties[k] == undefined) {
                    delete t.visibleProperties[k]
                }
            })
        })
        verifyData()
        tabManager.collection.update()
        // rerender()
    }

    function rerender() {
        status.renderNb += 1
    }

    async function uploadPropFile(file: any) {
        const res = await apiUploadPropFile(file)
        init()
        return res
    }

    function updatePropertyOptions() {
        for (let tabId in data.tabs) {
            const tab = data.tabs[tabId]
            if (tab.propertyOptions == undefined) {
                tab.propertyOptions = {}
            }
            for (let propId in data.properties) {
                tab.propertyOptions[propId] = Object.assign(defaultPropertyOption(), tab.propertyOptions[propId])
            }
        }
    }

    function getTabManager() {
        return tabManager
    }

    return {
        // variables
        data, status, openModal,

        // computed
        propertyList, imageList, folderRoots,

        // functions
        init, rerender,
        addProperty, deleteProperty, updateProperty, setPropertyValue,
        addTab, removeTab, updateTab, selectTab, getTab, getTabManager,
        addTag, deleteTagParent, updateTag, addTagParent,
        showModal, hideModal,
        uploadPropFile,
    }

})
