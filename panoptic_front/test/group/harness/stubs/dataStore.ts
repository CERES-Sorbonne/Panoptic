/**
 * Headless stand-in for @/data/stores/dataStore — only the property/tag indexes the group
 * engine reads. Properties are declared per test through setProperties/addTagProperty.
 */
import { PropertyType, deletedID, deletedName } from '@/data/models'

export const dataStub = {
    properties: {} as any,
    tags: {} as any,
    folders: {} as any,
}

/** Declare a simple (non-tag) property. */
export function setProperty(id: number, type: PropertyType, name = 'p' + id) {
    dataStub.properties[id] = { id, name, type }
}

/**
 * Declare a tag property. `tags` maps tag id → its parent ids; `allParents` is what the engine
 * reads to fan a tag out over its ancestors.
 */
export function setTagProperty(id: number, type: PropertyType, tags: { [tagId: number]: number[] }) {
    const index: any = {}
    for (const key of Object.keys(tags)) {
        const tagId = Number(key)
        index[tagId] = { id: tagId, propertyId: id, value: 't' + tagId, allParents: tags[tagId] }
    }
    dataStub.properties[id] = { id, name: 'p' + id, type, tags: index }
    dataStub.tags[id] = index
}

export function resetData() {
    dataStub.properties = {}
    dataStub.tags = {}
    dataStub.folders = {}
}

export function useDataStore() { return dataStub as any }

/**
 * Delete a tag the way dataStore.applyCommit's `emptyTags` branch does: the tag object is
 * TOMBSTONED in place, not removed. `property.tags` keeps the id as a key while the object it
 * points at stops naming that id. `hard` instead removes the entry, which is what the soft
 * delete was introduced to avoid — the tests say what each one breaks.
 */
export function deleteTagInStub(propId: number, tagId: number, hard = false) {
    const index = dataStub.properties[propId]?.tags
    if (!index?.[tagId]) return
    if (hard) {
        delete index[tagId]
        delete dataStub.tags[propId]?.[tagId]
        return
    }
    index[tagId].id = deletedID
    index[tagId].value = deletedName
}
