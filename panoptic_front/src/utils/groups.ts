import { Group, Image, PropertyType } from "@/data/models"
import { DefaultDict } from "./helpers"
import { globalStore } from "@/data/store"

export const UNDEFINED_KEY = '__undefined__'

// export function computeGroups(images: Array<Image>, propertyIds: number[]) {
//     let res = []
//     let rootGroup = {
//         name: '__all__',
//         images: images,
//         groups: [],
//         count: images.length,
//         propertyId: undefined
//     } as Group
//     if (propertyIds.length > 0) {
//         rootGroup = computeSubgroups(rootGroup, propertyIds)
//         res.push(...rootGroup.groups)
//     }
//     else {
//         res.push(rootGroup)
//     }
//     return res
// }


// function computeSubgroups(parentGroup: Group, propertyIds: number[]) {
//     let images = parentGroup.images
//     let propertyId = propertyIds[0]
//     let groups = new DefaultDict(Array) as { [k: string | number]: any }
//     let type = globalStore.properties[propertyId].type

//     for (let img of images) {
//         let value = propertyId in img.properties ? img.properties[propertyId].value : "undefined"
//         if (value == null || value == '') {
//             value = undefined
//         }
//         if (type == PropertyType.checkbox && value != true) {
//             value = false
//         }
//         if (Array.isArray(value)) {
//             value.forEach((v: any) => groups[v].push(img))
//         }
//         else {
//             groups[value].push(img)
//         }
//     }
//     let res = []
//     for (let group in groups) {
//         res.push({
//             name: group,
//             images: groups[group],
//             groups: undefined,
//             count: groups[group].length,
//             propertyId: propertyId,
//             depth: parentGroup.depth + 1,
//             parentId: parentGroup.id
//         })
//     }

//     if (propertyIds.length > 1) {
//         res.map(g => computeSubgroups(g, propertyIds.slice(1)))
//     }

//     parentGroup.groups = res
//     parentGroup.images = []
//     return parentGroup
// }