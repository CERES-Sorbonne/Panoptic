import { Group, Image, Property, PropertyType, Sort, SortIndex } from "@/data/models";
import { globalStore } from "@/data/store";
import { UNDEFINED_KEY } from "./groups";

function getSortFunction(type: PropertyType): any {
    switch (type) {
        case PropertyType.string:
        case PropertyType.url:
        case PropertyType.number:
        case PropertyType.path:
        case PropertyType._sha1:
        case PropertyType._ahash:
        case PropertyType.color:
        case PropertyType.date:
            return (a: any, b: any) => {
                if (a == undefined || a == '') return 1
                if (b == undefined || b == '') return -1
                return a < b ? -1 : a > b ? 1 : 0
            }
        case PropertyType.checkbox:
            return (a: any, b: any) => {
                if (a) {
                    return -1
                }
                if (a == b) {
                    return 0
                }
                return 1
            }
        case PropertyType.multi_tags:
            return (a: Array<string>, b: Array<string>) => {
                let al = Array.isArray(a) ? a.length : 0
                let bl = Array.isArray(b) ? b.length : 0
                return al - bl
            }
        case PropertyType.tag:
            return (a: string, b: string) => {
                if (a == undefined) return -1
                if (b == undefined) return 1
                return a < b ? -1 : a > b ? 1 : 0
            }
        default:
            return () => -1
    }
}

function getImageSortFunction2(sortList: Sort[]) {
    let sortFunctions = sortList.map(s => globalStore.properties[s.property_id].type).map(getSortFunction)

    function sortImages(img1: Image, img2: Image) {
        // console.log(sortList)
        // console.log(img1.properties, img2.properties)
        let res = 0
        for (let i = 0; i < sortFunctions.length; i++) {
            let sortFnc = sortFunctions[i]
            let property = globalStore.properties[sortList[i].property_id]
            const modif = sortList[i].ascending ? 1 : -1

            let p1 = img1.properties[property.id]?.value
            let p2 = img2.properties[property.id]?.value

            if (property.type == PropertyType.tag) {
                let t1 = Array.isArray(p1) && p1.length > 0 ? p1[0] : undefined
                let t2 = Array.isArray(p2) && p2.length > 0 ? p2[0] : undefined

                p1 = globalStore.tags[property.id][t1]?.value
                p2 = globalStore.tags[property.id][t2]?.value
            }

            res = sortFnc(p1, p2)
            if (res != 0) {
                return res * modif
            }
        }
        return res
    }
    return sortImages
}

export function sortImages(images: Array<Image>, sortList: Sort[]) {
    if (sortList.length == 0) {
        return images
    }
    let fnc = getImageSortFunction2(sortList)
    images.sort(fnc)
    return images
}

export function sortGroups(groups: Array<Group>, sortIndex: SortIndex) {
    if (groups.length == 0) {
        return groups
    }
    if (groups.some(g => g.propertyId == undefined)) {
        return groups
    }

    let property = globalStore.properties[groups[0].propertyId]
    let type = property.type
    if (type == PropertyType.multi_tags || type == PropertyType.tag) {
        type = PropertyType.tag // one group is one tag, we do alphabetical string comparaison when sorting groups
    }

    const sort = sortIndex[property.id]
    if (sort && sort.byGroupSize) {
        groups.sort((a: Group, b: Group) => {
            if (a.groups) {
                return a.groups.length - b.groups.length
            }
            return a.images.length - b.images.length
        })
    }
    else {
        let sortFnc = getSortFunction(type)
        groups.sort((a: Group, b: Group) => {
            let va = a.name as any
            let vb = b.name as any

            if (type == PropertyType.tag) {
                if (va == UNDEFINED_KEY) {
                    va = 'zzzzzzzzzzzzzzzzzz'
                } else {
                    va = globalStore.tags[property.id][va].value
                }
                if (vb == UNDEFINED_KEY) {
                    vb = 'zzzzzzzzzzzzzzzzzz'
                } else {
                    vb = globalStore.tags[property.id][vb].value
                }


            }
            return sortFnc(va, vb)
        })
    }

    if (sort && !sort.ascending) {
        groups.reverse()
    }

    return groups
}

export function sortGroupTree(group: Group, order: Array<string>, sortIndex: SortIndex) {
    order.push(group.id)
    if (group.groups && group.groups.length > 0) {
        sortGroups(group.groups, sortIndex)
        group.groups.forEach(g => sortGroupTree(g, order, sortIndex))
    }
}