import { Group } from "@/core/GroupManager"
import { PropertyType, Tag, Folder, Property, Instance, TagIndex } from "@/data/models"
import { useProjectStore } from "@/data/projectStore"
import { Ref, computed } from "vue"


export function hasProperty(image: Instance, propertyId: number) {
    return image.properties[propertyId] && image.properties[propertyId].value !== undefined
}


export function isTag(type: PropertyType) {
    return type == PropertyType.tag || type == PropertyType.multi_tags
}

export function getFolderAndParents(folder: Folder) {
    const project = useProjectStore()
    const res = []
    let current = folder
    while (current) {
        res.push(current.id)
        current = project.data.folders[current.parent]
    }
    return res
}

export function getFolderChildren(folderId: number) {
    const project = useProjectStore()
    let res: Folder[] = []
    const recursive = (fId: number) => {
        const children = project.data.folders[fId].children
        res.push(...children)
        children.forEach(c => recursive(c.id))
    }
    recursive(folderId)
    return res
}

export function computedPropValue(property: Ref<Property>, image: Ref<Instance>) {
    const propValue = computed(() => {
        if (!hasProperty(image.value, property.value.id)) {
            return undefined
        }
        return image.value.properties[property.value.id].value
    })
    return propValue
}


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

export function getTagChildren(tag: Tag, tags: TagIndex) {
    const res = []
    const recursive = (t: Tag) => {
        res.push(t.id)
        if (t.children) {
            t.children.forEach(cId => recursive(tags[cId]))
        }

    }
    recursive(tag)
    return res
}

export function getTagParents(tag: Tag, tags) {
    const res = []
    const recursive = (t: Tag) => {
        for (let pId of t.parents) {
            if (pId == 0) continue
            res.push(pId)
            recursive(tags[pId])
        }
    }
    recursive(tag)
    return res
}

// export async function getSimilarImagesFromText(context: ActionContext) {
//     return await apiGetSimilarImagesFromText(context)
// }

type ObjectValues<T> = T[keyof T][];

export function objValues<T>(obj: T): ObjectValues<T> {
    return Object.keys(obj).map(key => obj[key as keyof T]);
}

export function pad(num) {
    num = num.toString();
    if (num.length < 2) num = "0" + num;
    return num;
}

export function goNext() {
    let elem = document.getElementsByClassName('v-step__button-next')[0] as HTMLElement
    if (elem) {
        elem.click()
    }
}

// https://stackoverflow.com/questions/54242239/how-to-convert-snake-case-to-camelcase-in-typescripts
export function keysToCamel(o) {
    if (o === Object(o) && !Array.isArray(o) && typeof o !== 'function') {
        const n = {};
        Object.keys(o).forEach((k) => {
            n[toCamel(k)] = keysToCamel(o[k]);
        });
        return n;
    } else if (Array.isArray(o)) {
        return o.map((i) => {
            return keysToCamel(i);
        });
    }
    return o;
}

function toCamel(s: string): string {
    return s.replace(/([-_][a-z])/gi, ($1) => {
        return $1.toUpperCase().replace('-', '').replace('_', '');
    });
}

export function keysToSnake(o: unknown): unknown {
    if (o === Object(o) && !Array.isArray(o) && typeof o !== 'function') {
        const n = {};
        Object.keys(o).forEach((k) => {
            n[toSnake(k)] = keysToSnake(o[k]);
        });
        return n;
    } else if (Array.isArray(o)) {
        return o.map((i) => {
            return keysToSnake(i);
        });
    }
    return o;
}

function toSnake(s: string): string {
    return s.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

export function deepCopy<T>(source: T): T {
    if (source === null || typeof source !== 'object') {
        return source;
    }

    if (Array.isArray(source)) {
        const copy: any[] = [];
        for (const element of source) {
            copy.push(deepCopy(element));
        }
        return copy as any as T;
    }

    if (source instanceof Date) {
        return new Date(source.getTime()) as any as T;
    }

    if (source instanceof Map) {
        const copy = new Map();
        source.forEach((value, key) => {
            copy.set(deepCopy(key), deepCopy(value));
        });
        return copy as any as T;
    }

    if (source instanceof Set) {
        const copy = new Set();
        source.forEach((value) => {
            copy.add(deepCopy(value));
        });
        return copy as any as T;
    }

    const copy: { [key: string]: any } = {};
    for (const key in source) {
        if (source.hasOwnProperty(key)) {
            copy[key] = deepCopy(source[key]);
        }
    }

    return copy as T;
}

export function getComputedValues(instance: Instance) {
    const res = [ instance.id, instance.sha1, instance.ahash, instance.folderId, instance.width, instance.height, instance.url]
    return res;
}