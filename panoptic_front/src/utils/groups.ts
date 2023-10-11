import { Group, GroupIndex, Image, PropertyType, Sha1Pile } from "@/data/models"
import { DefaultDict } from "./helpers"
import { globalStore } from "@/data/store"
import moment from "moment"

export const UNDEFINED_KEY = '__undefined__'
export const MAX_GROUPS = 5

export function generateGroups(images: Image[], groups: number[]) {
    const index: GroupIndex = {}
    let rootGroup = {
        name: 'All',
        images: images,
        groups: undefined as Group[],
        count: images.length,
        propertyId: undefined,
        id: '0',
        depth: 0,
        parentId: undefined,
        propertyValues: []
    } as Group
    if (groups.length > 0) {
        rootGroup = computeSubgroups(rootGroup, groups, index)
    }
    index[rootGroup.id] = rootGroup
    return index
}


export function computeSubgroups(parentGroup: Group, groupList: number[], index: GroupIndex) {
    let images = parentGroup.images
    let propertyId = groupList[0]
    let groups = new DefaultDict(Array) as { [k: string | number]: any }
    let type = globalStore.properties[propertyId].type

    for (let img of images) {
        let value = propertyId in img.properties ? img.properties[propertyId].value : UNDEFINED_KEY
        if (value == null || value === '') {
            value = UNDEFINED_KEY
        }
        else if (type == PropertyType.checkbox && value != true) {
            value = false
        }

        if (Array.isArray(value)) {
            value.forEach((v: any) => groups[v].push(img))
        }
        else if (type == PropertyType.date) {
            groups[moment(value).format('YYYY/MM')].push(img)
        }
        else {
            groups[value].push(img)
        }
    }
    let res = [] as Group[]
    for (let key in groups) {
        let newGroup = {
            name: key,
            images: groups[key],
            groups: undefined as Group[],
            count: groups[key].length,
            propertyId: propertyId,
            id: parentGroup.id + '-' + propertyId + '-' + key,
            depth: parentGroup.depth + 1,
            parentId: parentGroup.id,
            propertyValues: [...parentGroup.propertyValues, { propertyId, value: key }]
        }
        res.push(newGroup)
    }

    if (groupList.length > 1) {
        res.map(g => computeSubgroups(g, groupList.slice(1), index))
    }

    parentGroup.groups = res
    parentGroup.children = res.map(g => g.id)
    parentGroup.images = []
    res.forEach(g => index[g.id] = g)
    return parentGroup
}

export function mergeGroup(update: Group, index: GroupIndex) {
    // console.log('merge: ' + update.id)

    let id = update.id

    if (index[id] == undefined) {
        return update
    }
    // console.log('closed: ' + index[id].closed)

    update.closed = index[id].closed
    let childrenIds = index[id].children
    if (!childrenIds || childrenIds.length == 0) {
        return update
    }

    // let children = childrenIds.map(id => index[id]).filter(c => c != undefined).filter(c => c.propertyId == undefined)
    let children = index[id].groups
    if ((Array.isArray(index[id].images) && index[id].images.length > 0 && children && children.length > 0)) {
        update.children = children.map(c => c.id)
        update.groups = children
    }
    return update
}

export function imagesToSha1Piles(group: Group) {
    const res: Array<Sha1Pile> = []
    const order: { [key: string]: number } = {}

    for (let img of group.images) {
        if (order[img.sha1] === undefined) {
            order[img.sha1] = res.length
            res.push({ sha1: img.sha1, images: [] })
        }
        res[order[img.sha1]].images.push(img)
    }

    group.imagePiles = res
    // group.images = []
}