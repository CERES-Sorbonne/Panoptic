import { buildGroup, Group, GroupType } from "@/core/GroupManager"
import { TabManager } from "@/core/TabManager"
import { deletedID, useDataStore } from "@/data/dataStore"
import { PropertyType, Tag, Folder, Property, Instance, TagIndex, ActionContext, GroupResult, ScoreIndex, InstanceIndex, Sha1ToInstances, GroupScoreList, LoadState, DbCommit } from "@/data/models"
import { useProjectStore } from "@/data/projectStore"
import { Ref, computed, inject, ref, watch } from "vue"
import chroma from 'chroma-js';

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

export function keysToCamel(o) {
    // 1. Base Case: If the value is null, undefined, or a primitive (string, number, boolean)
    if (typeof o !== 'object' || o === null) {
        return o;
    }

    // 2. Array Case
    if (Array.isArray(o)) {
        // Use map, as in your original code
        return o.map(i => keysToCamel(i));
    }

    // 3. Object Case (using a more specific check for plain objects)
    // We check constructor to exclude Dates, custom classes, etc., which might pass the 'Object(o)' test.
    if (o.constructor === Object) {
        const n = {};
        for (const k in o) {
            if (Object.prototype.hasOwnProperty.call(o, k)) {
                // Use the memoized 'toCamel' function
                n[toCamel(k)] = keysToCamel(o[k]);
            }
        }
        return n;
    }

    // Return other complex types (like Date, Map, custom classes) unprocessed
    return o;
}

// A simple cache outside the main function scope
const camelCaseCache = {};

function toCamel(s) {
    if (camelCaseCache[s]) {
        return camelCaseCache[s];
    }

    // Assuming 's' is 'snake_case' or 'kebab-case'
    const result = s.replace(/([-_][a-z])/ig, ($1) => {
        return $1.toUpperCase()
            .replace('-', '')
            .replace('_', '');
    });

    camelCaseCache[s] = result; // Store result
    return result;
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

export function convertSearchGroupResult(groups: GroupResult[]) {
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
    if (!group.scores) return

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
    if (!state) return false

    return state.finishedProperty &&
        state.finishedInstance &&
        state.finishedTags &&
        state.finishedInstanceValues &&
        state.finishedImageValues &&
        state.finishedPropertyGroups
}

export function sourceFromFunction(func: string) {
    return func.slice(0, func.indexOf('.'))
}

export function hasPropertyChanges(commit: DbCommit) {
    return commit.properties?.length || commit.emptyProperties?.length || commit.propertyGroups?.length || commit.emptyPropertyGroups?.length
}

export function useEventSignal() {
    const signal = ref(0)
    let data = null

    const emit = (payload?: any) => {
        data = payload
        signal.value++
    }

    const on = (callback) => {
        // watch auto-cleans up when component unmounts
        watch(signal, () => callback(data), { flush: 'sync' })
    }

    return { emit, on }
}

/**
 * Generates an array of visually distinct colors by distributing them equally around the HSL color wheel.
 *
 * @param nb_groups The number of distinct colors to generate.
 * @returns An array of color strings in Hexadecimal format (e.g., '#FF0000').
 */
export function generateColors(nb_groups: number): string[] {
    if (nb_groups <= 0) {
        return [];
    }
    if (nb_groups <= 20) {
        return PALETTE_20.slice(0, nb_groups);
    }
    return generateChromaColors(nb_groups)
}

const PALETTE_20 = [
    '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
    '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe',
    '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000',
    '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080'
];

/**
 * Generates an array of perceptually distinct colors using HCL color space.
 * Uses the golden angle for hue distribution and cycles through luminance/chroma
 * variations to maximize perceptual distance between colors.
 *
 * @param nb_groups The number of distinct colors to generate.
 * @returns An array of color strings in Hexadecimal format (e.g., '#FF0000').
 */
export function generateChromaColors(nb_groups: number): string[] {
    if (nb_groups <= 0) {
        return [];
    }

    const colors: string[] = [];
    const goldenAngle = 137.508; // Golden angle for optimal hue distribution

    // For small numbers, use predefined highly distinct colors
    if (nb_groups <= 8) {
        const presetHues = [0, 240, 60, 300, 120, 30, 180, 270];
        for (let i = 0; i < nb_groups; i++) {
            const luminance = 65 + (i % 2) * 20; // Alternate 65/85
            const chromaValue = 70 + (i % 2) * 20; // Alternate 70/90
            const color = chroma.hcl(presetHues[i], chromaValue, luminance);
            colors.push(color.hex().toUpperCase());
        }
        return colors;
    }

    // For larger numbers, use a multi-dimensional approach
    // We'll cycle through different luminance and chroma levels systematically
    const luminanceLevels = [50, 65, 80]; // Dark, medium, light
    const chromaLevels = [50, 70, 90];    // Low, medium, high saturation
    
    // Calculate how many hue variations we need
    const totalCombinations = luminanceLevels.length * chromaLevels.length;
    const hueStep = Math.ceil(nb_groups / totalCombinations);

    for (let i = 0; i < nb_groups; i++) {
        // Distribute hue using golden angle
        const hue = (i * goldenAngle) % 360;
        
        // Cycle through luminance and chroma systematically
        // This ensures adjacent colors differ in multiple dimensions
        const lumIndex = Math.floor(i / chromaLevels.length) % luminanceLevels.length;
        const chromaIndex = i % chromaLevels.length;
        
        const luminance = luminanceLevels[lumIndex];
        const chromaValue = chromaLevels[chromaIndex];

        // Create color in perceptually uniform HCL space
        const color = chroma.hcl(hue, chromaValue, luminance);
        
        // Ensure the color is valid (some HCL combinations may be out of RGB gamut)
        if (color.clipped()) {
            // If clipped, adjust chroma downward until valid
            let adjustedChroma = chromaValue;
            let adjustedColor = color;
            while (adjustedColor.clipped() && adjustedChroma > 0) {
                adjustedChroma -= 5;
                adjustedColor = chroma.hcl(hue, adjustedChroma, luminance);
            }
            colors.push(adjustedColor.hex().toUpperCase());
        } else {
            colors.push(color.hex().toUpperCase());
        }
    }

    return colors;
}

// ----------------------------------------------------------------------
// HELPER: HSL to HEX Conversion (Required for standard web output)
// ----------------------------------------------------------------------

/**
 * Converts HSL values to a standard Hexadecimal color string.
 * This helper function ensures the output is in the widely used #RRGGBB format.
 * * @param h Hue (0-360)
 * @param s Saturation (0-100)
 * @param l Lightness (0-100)
 * @returns Hexadecimal color string (e.g., '#FF0000')
 */
function hslToHex(h: number, s: number, l: number): string {
    // Convert S and L from percentage to decimal (0-1)
    s /= 100;
    l /= 100;

    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs((h / 60) % 2 - 1));
    const m = l - c / 2;
    let r = 0, g = 0, b = 0;

    if (h >= 0 && h < 60) {
        r = c; g = x; b = 0;
    } else if (h >= 60 && h < 120) {
        r = x; g = c; b = 0;
    } else if (h >= 120 && h < 180) {
        r = 0; g = c; b = x;
    } else if (h >= 180 && h < 240) {
        r = 0; g = x; b = c;
    } else if (h >= 240 && h < 300) {
        r = x; g = 0; b = c;
    } else if (h >= 300 && h < 360) {
        r = c; g = 0; b = x;
    }

    // Convert R, G, B from (0-1) + m to (0-255)
    r = Math.round((r + m) * 255);
    g = Math.round((g + m) * 255);
    b = Math.round((b + m) * 255);

    const toHex = (c: number) => c.toString(16).padStart(2, '0');

    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

export function getBoundingRect(points: {x: number, y: number}[]) {
    if (!points || points.length === 0) {
        return null;
    }

    // Initialize min/max values using the coordinates of the first point.
    let minX = points[0].x;
    let minY = points[0].y;
    let maxX = points[0].x;
    let maxY = points[0].y;

    // Iterate over the rest of the points to find the true extremes.
    for (let i = 1; i < points.length; i++) {
        const point = points[i];

        // Find the overall minimum X
        if (point.x < minX) {
            minX = point.x;
        }

        // Find the overall maximum X
        if (point.x > maxX) {
            maxX = point.x;
        }

        // Find the overall minimum Y
        if (point.y < minY) {
            minY = point.y;
        }

        // Find the overall maximum Y
        if (point.y > maxY) {
            maxY = point.y;
        }
    }

    // Calculate dimensions
    const width = maxX - minX;
    const height = maxY - minY;

    return {
        minX,
        minY,
        maxX,
        maxY,
        width,
        height
    };
}