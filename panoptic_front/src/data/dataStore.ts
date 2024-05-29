import { defineStore } from "pinia";
import { computed, shallowRef, triggerRef } from "vue";
import { DbCommit, ImagePropertyValue, Instance, InstanceIndex, InstancePropertyValue, Property, PropertyIndex, PropertyMode, PropertyType, Sha1ToImages, Sha1ToInstances, Tag, TagIndex } from "./models";
import { objValues } from "./builder";
import { SERVER_PREFIX } from "./api";
import { computeContainerRatio, setTagsChildren } from "./storeutils";
import { getComputedValues, getTagChildren, getTagParents } from "@/utils/utils";

const deletedID = -999999999
const deletedName = 'Deleted'

export const useDataStore = defineStore('dataStore', () => {

    const instances = shallowRef<InstanceIndex>({})
    const properties = shallowRef<PropertyIndex>({})
    const tags = shallowRef<TagIndex>({})

    const sha1Index = shallowRef<Sha1ToInstances>({})
    const instanceList = computed(() => objValues(instances.value))
    const propertyList = computed(() => objValues(properties.value))

    function importInstances(toImport: Instance[]) {
        for (let img of toImport) {
            const values = getComputedValues(img)
            img.fullUrl = SERVER_PREFIX + '/images/' + img.url
            img.url = SERVER_PREFIX + '/small/images/' + img.sha1 + '.jpeg'
            img.containerRatio = computeContainerRatio(img)

            if (instances.value[img.id]) {
                img.properties = Object.assign(instances.value[img.id].properties, img.properties)
            }
            else {
                if (!Array.isArray(sha1Index.value[img.sha1])) {
                    sha1Index.value[img.sha1] = []
                }
                sha1Index.value[img.sha1].push(img)

            }
            for (let i = 0; i < values.length; i++) {
                img.properties[-i - 1] = values[i]
            }
            instances.value[img.id] = img
        }
    }

    function importProperties(toImport: Property[]) {
        for (let property of toImport) {
            if (property.id in properties.value) {
                property.tags = properties.value[property.id].tags
            }
            properties.value[property.id] = property
        }
    }

    function importTags(toImport: Tag[]) {
        const updated = new Set<number>()
        for (let tag of toImport) {
            tag.parents = tag.parents.filter(p => p != 0)
            tags.value[tag.id] = tag
            if (!(tag.propertyId in properties.value)) {
                console.warn('Property ' + tag.propertyId + ' must be loaded before importing tags')
                continue
            }
            if (!properties.value[tag.propertyId].tags) {
                properties.value[tag.propertyId].tags = {}
            }
            properties.value[tag.propertyId].tags[tag.id] = tag
            updated.add(tag.propertyId)

        }
        for (let propId of updated) {
            setTagsChildren(properties.value[propId].tags)
        }
        for (let tag of toImport) {
            tag.allChildren = getTagChildren(tag, tags.value)
            tag.allChildren.splice(tag.allChildren.indexOf(tag.id), 1)
            tag.allParents = getTagParents(tag, tags.value)
        }
        // computeTagCount()
    }

    function importInstanceValues(instanceValues: InstancePropertyValue[]) {
        for (let v of instanceValues) {
            if (v.value == undefined) continue
            instances.value[v.instanceId].properties[v.propertyId] = v.value
        }
    }

    function importImageValues(instanceValues: ImagePropertyValue[]) {
        for (let v of instanceValues) {
            if (v.value == undefined) continue
            for (let img of sha1Index.value[v.sha1]) {
                instances.value[img.id].properties[v.propertyId] = v.value
            }
        }
    }

    function applyCommit(commit: DbCommit) {
        if (commit.emptyImageValues) {
            commit.emptyImageValues.forEach(v => {
                sha1Index.value[v.sha1].forEach(i => {
                    delete instances.value[i.id].properties[v.propertyId]
                })
            })
        }
        if (commit.emptyInstanceValues) {
            commit.emptyInstanceValues.forEach(v => {
                delete instances.value[v.instanceId].properties[v.propertyId]
            })
        }
        if (commit.emptyTags) {
            commit.emptyTags.forEach(i => {
                tags.value[i].id = deletedID
                tags.value[i].value = deletedName
            })
        }
        if (commit.emptyProperties?.length) {
            commit.emptyProperties.forEach(i => {
                properties.value[i].id = deletedID
                properties.value[i].name = deletedName
            })
        }
        if (commit.emptyInstances) {
            // TODO: ??
        }

        if (commit.instances?.length) {
            importInstances(commit.instances)
        }
        if (commit.properties?.length) {
            importProperties(commit.properties)
        }
        if (commit.tags?.length) {
            importTags(commit.tags)
        }
        if (commit.instanceValues?.length) {
            importInstanceValues(commit.instanceValues)
        }
        if (commit.imageValues?.length) {
            importImageValues(commit.imageValues)
        }
        triggerRef(instances)
    }

    return {
        instances, properties, tags,
        instanceList, propertyList,
        applyCommit
    }

})