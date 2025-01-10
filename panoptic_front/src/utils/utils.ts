import { buildGroup, Group, GroupType } from "@/core/GroupManager"
import { TabManager } from "@/core/TabManager"
import { deletedID, useDataStore } from "@/data/dataStore"
import { PropertyType, Tag, Folder, Property, Instance, TagIndex, ActionContext, GroupResult, ScoreIndex, InstanceIndex, Sha1ToInstances, GroupScoreList, LoadState } from "@/data/models"
import { useProjectStore } from "@/data/projectStore"
import { Ref, computed, inject } from "vue"


export function hasProperty(image: Instance, propertyId: number) {
    return image.properties[propertyId] && image.properties[propertyId].value !== undefined
}


export function isTag(type: PropertyType) {
    return type == PropertyType.tag || type == PropertyType.multi_tags
}

export function getFolderAndParents(folder: Folder) {
    const data = useDataStore()
    const res = []
    let current = folder
    while (current) {
        res.push(current.id)
        current = data.folders[current.parent]
    }
    return res
}

export function getFolderChildren(folderId: number) {
    const data = useDataStore()
    let res: Folder[] = []
    const recursive = (fId: number) => {
        const children = data.folders[fId].children
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
            t.children.filter(c => c != deletedID).forEach(cId => recursive(tags[cId]))
        }

    }
    recursive(tag)
    return res
}

export function getTagParents(tag: Tag, tags) {
    const res = []
    const recursive = (t: Tag) => {
        if (!t) return
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
    const res = [instance.id, instance.sha1, instance.ahash, instance.folderId, instance.width, instance.height, instance.url]
    return res;
}


export function computeTagToInstance(instances: Instance[], properties: Property[], tags: Tag[], tagIndex: TagIndex) {
    const res: { [tId: number]: Instance[] } = {}

    for (let tag of tags) {
        res[tag.id] = []
    }

    for (let instance of instances) {
        for (let property of properties) {
            let value = instance.properties[property.id]
            if (value === undefined) continue
            if (!Array.isArray(value)) {
                value = [value]
            }
            const allTags = new Set<number>()
            for (let tId of value) {
                tagIndex[tId].allParents.forEach(p => allTags.add(p))
                allTags.add(tId)
            }
            Array.from(allTags).forEach(tId => {
                res[tId].push(instance)
            })
        }
    }
    return res
}

export const sum = arr => arr.reduce((a, num) => a + num, 0);

export function numberToString(number: number, minLength: number) {
    let str = String(number)
    let prefix = ''
    if (str[0] == '-') {
        prefix = '-'
        str = str.substring(1)
    }
    let missing = minLength - str.length
    if (missing) {
        for (let i = 0; i < missing; i++) {
            str = "0" + str
        }
    }
    return prefix + str
}

export function adjustForTimezone(date: Date): Date {
    var timeOffsetInMS: number = date.getTimezoneOffset() * 60000;
    console.log(timeOffsetInMS)
    date.setTime(date.getTime() - timeOffsetInMS);
    return date
}

export function allChildrenSha1Groups(group: Group) {
    function recursive(child: Group) {
        if (!child.isSha1Group && child.type != GroupType.Sha1) {
            return false
        }
        if (child.children) {
            return child.children.every(allChildrenSha1Groups)
        }
        return true
    }
    return group.children.every(recursive)
}

export function convertClusterGroupResult(groups: GroupResult[], ctx: ActionContext) {
    const data = useDataStore()
    const sha1Index: { [key: string]: number[] } = {}

    ctx.instanceIds.forEach(id => {
        const sha1 = data.instances[id].sha1
        if (!sha1Index[sha1]) sha1Index[sha1] = []
        sha1Index[sha1].push(id)
    })

    return groups.map((group) => {
        let instances: Instance[] = []
        const scoreIndex: { [sha1: string]: number } = {}
        if (group.ids) {
            instances = group.ids.map(i => data.instances[i])
        } else {
            if (group.scores) {
                group.sha1s.forEach((sha1, i) => {
                    scoreIndex[sha1] = group.scores.values[i]
                })
            }
            group.sha1s.forEach(sha1 => sha1Index[sha1].forEach(i => instances.push(data.instances[i])))
        }
        const res = buildGroup(data.getTmpId(), instances, GroupType.Cluster)
        res.meta.score = Math.round(group.score?.value ?? undefined)
        res.name = group.name
        res.isSha1Group = group.ids ? false : true
        res.score = group.score
        res.scores = convertScoreListToGroupScoreList(group, data.sha1Index)

        return res
    })
}

export function convertSearchGroupResult(groups: GroupResult[], ctx: ActionContext) {
    const data = useDataStore()

    return groups.map((group) => {
        let instances: Instance[] = []
        const scoreIndex: { [sha1: string]: number } = {}
        if (group.ids) {
            instances = group.ids.map(i => data.instances[i])
        } else {
            if (group.scores) {
                group.sha1s.forEach((sha1, i) => {
                    scoreIndex[sha1] = group.scores.values[i]
                })
            }
            group.sha1s.forEach(sha1 => data.sha1Index[sha1].forEach(i => instances.push(i)))
        }
        const res = buildGroup(data.getTmpId(), instances, GroupType.Cluster)
        res.meta.score = Math.round(group.score?.value)
        res.name = group.name
        res.isSha1Group = group.ids ? false : true
        res.score = group.score
        res.scores = convertScoreListToGroupScoreList(group, data.sha1Index)
        return res
    })
}

export function sortGroupByScore(group: Group) {
    let dir = group.scores.maxIsBest ? -1 : 1
    group.images.sort((i1, i2) => {
        return (group.scores.valueIndex[i1.id] - group.scores.valueIndex[i2.id]) * dir
    })
    return group
}

export function convertScoreListToGroupScoreList(group: GroupResult, sha1Index: Sha1ToInstances) {
    if(!group.scores) return

    const index: ScoreIndex = {}
    if (group.sha1s) {
        for (let i = 0; i < group.sha1s.length; i++) {
            let sha1 = group.sha1s[i]
            for (let instance of sha1Index[sha1]) {
                index[instance.id] = group.scores.values[i]
            }
        }
    }
    if (group.ids) {
        group.ids.forEach((id, i) => {
            index[id] = group.scores.values[i]
        })
    }
    const scores: GroupScoreList = {
        min: group.scores.min,
        max: group.scores.max,
        maxIsBest: group.scores.maxIsBest,
        valueIndex: index,
        description: group.scores.description
    }
    return scores
}

export function isFinished(state: LoadState): boolean {
    if(!state) return false

    return state.finishedProperty && 
           state.finishedInstance && 
           state.finishedTags && 
           state.finishedInstanceValues && 
           state.finishedImageValues && 
           state.finishedPropertyGroups
}