import { Folder, Image, Property, PropertyMode, PropertyRef, Tag, TreeTag, isTag } from "@/data/models"
import { globalStore } from "@/data/store"
import { Ref, computed } from "vue"

export function hasProperty(image: Image, propertyId: number) {
    return image.properties[propertyId] && image.properties[propertyId].value !== undefined
}

export function getImageProperties(id: number) {
    const img = globalStore.images[id]
    let res = globalStore.propertyList.filter(p => p.mode == PropertyMode.id).map(p => {
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
    const img = globalStore.images[imgId]
    const p = globalStore.properties[propId]
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


export function isTagId(propId: number) {
    return isTag(globalStore.properties[propId].type)
}

export function getTagChildren(tag: Tag) {
    const node = globalStore.tagNodes[tag.property_id][tag.id]
    // console.log(node)

    let children = new Set()
    const recursive = (t: TreeTag) => {
        children.add(t.id)
        if (!t.children) return
        t.children.forEach(c => children.add(c.id))
        t.children.forEach(c => recursive(c))
    }
    recursive(node)

    return children
}

export function getFolderAndParents(folder: Folder, parents: number[] = []) {
    parents.push(folder.id)
    if (folder.parent != undefined) {
        parents = getFolderAndParents(globalStore.folders[folder.parent], parents)
    }
    return parents
}

export function getFolderParents(folderId: number) {
    const res: Folder[] = []
    const recursive = (fId: number) => {
        const parent = globalStore.folders[fId].parent
        if (parent != undefined) {
            res.push(globalStore.folders[parent])
            recursive(parent)
        }
    }
    recursive(folderId)
    return res
}

export function getFolderChildren(folderId: number) {
    let res: Folder[] = []
    const recursive = (fId: number) => {
        const children = globalStore.folders[fId].children
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
  }