import { ImagePropertyValue, InstancePropertyValue, isReadonly, Property, PropertyMode, PropertyType } from '@/data/models'
import { useDataStore } from '@/data/stores/dataStore'
import { useColumnStore } from '@/data/stores/columnStore'
import { isTag } from '@/utils/utils'

// Tag properties the map's tag brush can write. File-mode values go through another commit path.
export function paintableProperty(p: Property) {
    return p.id >= 0 && isTag(p.type) && !isReadonly(p) && p.mode !== PropertyMode.file
}

function nextValue(type: PropertyType, old: number[], tagId: number, remove: boolean): number[] {
    if (remove) return old.filter(t => t !== tagId)
    if (type === PropertyType.tag) return [tagId]
    return old.includes(tagId) ? old : [...old, tagId]
}

function sameTags(a: number[], b: number[]) {
    return a.length === b.length && a.every(t => b.includes(t))
}

/**
 * Adds `tagId` to (or removes it from) every instance of the given images, in a single commit so
 * one brush stroke is one undo step. Images whose value would not change are left out.
 *
 * Current values come from the full column, which commits and undos keep up to date (the map's
 * highlight reads it too). The instance store would miss them: it keeps no entry for an instance
 * fetched while it had no value.
 */
export async function paintTag(propertyId: number, tagId: number, sha1s: string[], remove: boolean) {
    const data = useDataStore()
    const columnStore = useColumnStore()
    const property = data.properties[propertyId]
    if (!property || !paintableProperty(property)) return

    await columnStore.requireFullColumn(propertyId)
    const idsBySha1 = sha1s.map(sha1 => columnStore.getInstancesBySha1(sha1))
    const current = (id: number): number[] => {
        const slot = columnStore.slotMap.get(id)
        const value = slot === undefined ? null : columnStore.readSlot(propertyId, slot)
        return Array.isArray(value) ? value : []
    }

    const instanceValues: InstancePropertyValue[] = []
    const imageValues: ImagePropertyValue[] = []
    sha1s.forEach((sha1, i) => {
        const ids = idsBySha1[i]
        if (property.mode === PropertyMode.sha1) {
            if (!ids.length) return
            const old = current(ids[0])
            const value = nextValue(property.type, old, tagId, remove)
            if (!sameTags(old, value)) imageValues.push({ propertyId, sha1, value })
            return
        }
        for (const instanceId of ids) {
            const old = current(instanceId)
            const value = nextValue(property.type, old, tagId, remove)
            if (!sameTags(old, value)) instanceValues.push({ propertyId, instanceId, value })
        }
    })
    if (!instanceValues.length && !imageValues.length) return
    await data.setPropertyValues(instanceValues, imageValues)
}
