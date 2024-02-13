import { Group } from "@/core/GroupManager"
import { apiGetMLGroups, apiGetSimilarImages, apiGetSimilarImagesFromText } from "@/data/api"
import { PropertyMode, PropertyRef, Image, PropertyType, Tag, Folder, Property, ActionContext } from "@/data/models"
import { useProjectStore } from "@/data/projectStore"
import { Exception } from "sass"
import { Ref, computed } from "vue"

export function hasProperty(image: Image, propertyId: number) {
    return image.properties[propertyId] && image.properties[propertyId].value !== undefined
}

export function getImageProperties(id: number) {
    const store = useProjectStore()
    const img = store.data.images[id]
    let res = store.propertyList.filter(p => p.mode == PropertyMode.id).map(p => {
        let propRef: PropertyRef = {
            propertyId: p.id,
            type: p.type,
            value: hasProperty(img, p.id) ? img.properties[p.id].value : undefined,
            imageId: img.id,
            mode: p.mode
        }
        return propRef
    })
    return res
}

export function getImageProperty(imgId: number, propId: number) {
    const store = useProjectStore()
    const img = store.data.images[imgId]
    const p = store.data.properties[propId]
    const propRef: PropertyRef = {
        propertyId: p.id,
        type: p.type,
        value: hasProperty(img, p.id) ? img.properties[p.id].value : undefined,
        imageId: img.id,
        mode: p.mode
    }
    return propRef
}

// export function isImageGroup(group: Group) {
//     return Array.isArray(group.images) && group.images.length > 0
// }

// export function isPileGroup(group: Group) {
//     return Array.isArray(group.imagePiles) && group.imagePiles.length > 0
// }

export function isTag(type: PropertyType) {
    return type == PropertyType.tag || type == PropertyType.multi_tags
}

export function isTagId(propId: number) {
    const store = useProjectStore()
    return isTag(store.data.properties[propId].type)
}

export function getChildren(tag: Tag) {
    const store = useProjectStore()
    const property = store.data.properties[tag.property_id]
    const tags = property.tags

    let children = new Set()
    const recursive = (t: Tag) => {
        children.add(t.id)
        if (!t.children) return
        t.children.forEach(cId => children.add(cId))
        t.children.forEach(cId => recursive(tags[cId]))
    }
    recursive(tag)

    return children
}

export function getFolderAndParents(folder: Folder) {
    const store = useProjectStore()
    const res = []
    let current = folder
    while (current) {
        res.push(current.id)
        current = store.data.folders[current.parent]
    }
    return res
}

export function getFolderChildren(folderId: number) {
    const store = useProjectStore()
    let res: Folder[] = []
    const recursive = (fId: number) => {
        const children = store.data.folders[fId].children
        res.push(...children)
        children.forEach(c => recursive(c.id))
    }
    recursive(folderId)
    return res
}

export function computedPropValue(property: Ref<Property>, image: Ref<Image>) {
    const propValue = computed(() => {
        if (!hasProperty(image.value, property.value.id)) {
            return undefined
        }
        return image.value.properties[property.value.id].value
    })
    return propValue
}

// export function computedPropValue(property: Property, image: Image) {
//     // return computed(() => {
//         if (!hasProperty(image, property.id)) {
//             return undefined
//         }
//         return image.properties[property.id].value
//     // })
// }

export function arrayEqual(arr1: any[], arr2: any[]) {
    const set1 = new Set(arr1)
    const set2 = new Set(arr2)
    return set1.size == set2.size && arr2.every(v => set1.has(v))
}

export const sleep = m => new Promise(r => setTimeout(r, m))

export class EventEmitter {
    private listeners: Function[];

    constructor() {
        this.listeners = []
    }

    addListener(listener: Function) {
        this.listeners.push(listener);
    }

    removeListener(listener: Function) {
        const index = this.listeners.indexOf(listener);
        if (index !== -1) {
            this.listeners.splice(index, 1);
        }
    }

    emit(value?: any) {
        this.listeners.forEach(listener => listener(value));
    }

    clear() {
        this.listeners.length = 0
    }
}

export function getGroupParents(group: Group): Group[] {
    const res = []
    let parent = group.parent
    while (parent) {
        res.push(parent)
        parent = parent.parent
    }
    return res
}

export function getTagChildren(tag: Tag) {
    const store = useProjectStore()
    const property = store.data.properties[tag.property_id]
    const tags = property.tags

    const res = []
    const recursive = (t: Tag) => {
        res.push(t.id)
        t.children.forEach(cId => recursive(tags[cId]))
    }
    recursive(tag)
    return res
}

export async function computeMLGroups(context: ActionContext) {
    let res = await apiGetMLGroups(context)
    return res
}

export async function getSimilarImagesFromText(context: ActionContext) {
    return await apiGetSimilarImagesFromText(context)
}

type ObjectValues<T> = T[keyof T][];

export function objValues<T>(obj: T): ObjectValues<T> {
    return Object.keys(obj).map(key => obj[key as keyof T]);
}

export function pad(num) {
    num = num.toString();
    if (num.length < 2) num = "0" + num;
    return num;
}