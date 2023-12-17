// import { Image, PropertyType, Sha1Pile } from "@/data/models"
// import { DefaultDict } from "./helpers"
// import { globalStore } from "@/data/store"
// import moment from "moment"

// export const UNDEFINED_KEY = '__undefined__'
// export const MAX_GROUPS = 5


// export function createGroup(name = 'All', images = []) {
//     let group = {
//         name: name,
//         images: images,
//         groups: undefined,
//         count: images.length,
//         propertyId: undefined,
//         id: '0',
//         depth: 0,
//         parentId: undefined,
//         propertyValues: []
//     }
//     return group
// }

// export function initArrayIfUndefined(data, key) {
//     if (data[key] === undefined) {
//         data[key] = []
//     }
// }

// export function generateGroupData(images: Image[], groups: number[], sha1Mode = false) {
//     let index = generateGroups(images, groups)
//     let root = index['0']
//     let order = Object.keys(index)

//     let imageToGroups = {}
//     for (let grpId in index) {
//         if (!index[grpId].images.length) continue

//         index[grpId].images.forEach(i => {
//             initArrayIfUndefined(imageToGroups, i.id)
//             imageToGroups[i.id].push(grpId)
//         })

//         if (sha1Mode) {
//             imagesToSha1Piles(index[grpId])
//         }
//     }
//     const data = { index, root, order, imageToGroups }
//     updateOrder(data)
//     return data
// }

// export function generateGroups(images: Image[], groups: number[]) {
//     const index= {}
//     let rootGroup = {
//         name: 'All',
//         images: images,
//         groups: undefined,
//         count: images.length,
//         propertyId: undefined,
//         id: '0',
//         depth: 0,
//         parentId: undefined,
//         propertyValues: []
//     } 
//     if (groups.length > 0) {
//         rootGroup = computeSubgroups(rootGroup, groups, index)
//     }
//     index[rootGroup.id] = rootGroup
//     return index
// }


// export function computeSubgroups(parentGroup, groupList: number[], index) {
//     console.log('gen sub', groupList)
//     let images = parentGroup.images
//     let propertyId = groupList[0]
//     let groups = new DefaultDict(Array) as { [k: string | number]: any }
//     let type = globalStore.properties[propertyId].type

//     for (let img of images) {
//         let value = propertyId in img.properties ? img.properties[propertyId].value : UNDEFINED_KEY
//         if (value == null || value === '') {
//             value = UNDEFINED_KEY
//         }
//         else if (type == PropertyType.checkbox && value != true) {
//             value = false
//         }

//         if (Array.isArray(value)) {
//             value.forEach((v: any) => groups[v].push(img))
//         }
//         else if (type == PropertyType.date) {
//             groups[moment(value).format('YYYY/MM')].push(img)
//         }
//         else {
//             groups[value].push(img)
//         }
//     }
//     let res = []
//     for (let key in groups) {
//         let newGroup = {
//             name: key,
//             images: groups[key],
//             groups: undefined,
//             count: groups[key].length,
//             propertyId: propertyId,
//             id: parentGroup.id + '-' + propertyId + '-' + key,
//             depth: parentGroup.depth + 1,
//             parentId: parentGroup.id,
//             propertyValues: [...parentGroup.propertyValues, { propertyId, value: key == UNDEFINED_KEY ? undefined : key }]
//         }
//         res.push(newGroup)
//     }

//     if (groupList.length > 1) {
//         res.map(g => computeSubgroups(g, groupList.slice(1), index))
//     }

//     parentGroup.groups = res
//     parentGroup.children = res.map(g => g.id)
//     parentGroup.images = []
//     res.forEach(g => index[g.id] = g)
//     console.log(parentGroup)
//     return parentGroup
// }

// export function updateOrder(data) {
//     for(let i = 0; i < data.order.length; i++) {
//         const groupId = data.order[i]
//         const group = data.index[groupId]
//         group.order = i
//     }
// }

// export function mergeGroup(update, index) {
//     // console.log('merge: ' + update.id)

//     let id = update.id

//     if (index[id] == undefined) {
//         return update
//     }
//     // console.log('closed: ' + index[id].closed)

//     update.closed = index[id].closed
//     let childrenIds = index[id].children
//     if (!childrenIds || childrenIds.length == 0) {
//         return update
//     }

//     // let children = childrenIds.map(id => index[id]).filter(c => c != undefined).filter(c => c.propertyId == undefined)
//     let children = index[id].groups
//     if ((Array.isArray(index[id].images) && index[id].images.length > 0 && children && children.length > 0)) {
//         update.children = children.map(c => c.id)
//         update.groups = children
//     }
//     return update
// }

// export function imagesToSha1Piles(group) {
//     const res: Array<Sha1Pile> = []
//     const order: { [key: string]: number } = {}

//     for (let img of group.images) {
//         if (order[img.sha1] === undefined) {
//             order[img.sha1] = res.length
//             res.push({ sha1: img.sha1, images: [] })
//         }
//         res[order[img.sha1]].images.push(img)
//     }

//     group.imagePiles = res
//     // group.images = []
// }



// export class ImageIterator {
//     groupIndex: number
//     imageIndex: number
//     data: any

//     constructor(data, groupIndex = 0, imageIndex = 0) {
//         this.data = data
//         this.groupIndex = groupIndex
//         this.imageIndex = imageIndex
//     }

//     clone() {
//         return new ImageIterator(this.data, this.groupIndex, this.imageIndex)
//     }

//     goToImage(groupId: string, imageId: number) {
//         this.groupIndex = this.data.order.findIndex(gId => gId === groupId)
//         if (this.groupIndex < 0) {
//             return false
//         }
//         const group = this.data.index[groupId]
//         // if(isPileGroup(group)) {
//         //     const sha1 = globalStore.images[imageId].sha1
//         //     this.imageIndex = group.imagePiles.findIndex(p => p.sha1 == sha1)
//         // } else {
//         //     this.imageIndex = group.images.findIndex(i => i.id == imageId)
//         //     if (this.imageIndex < 0) {
//         //         return false
//         //     }
//         // }

//         return true
//     }

//     getGroup() {
//         return this.data.index[this.data.order[this.groupIndex]]
//     }
//     getImages() {
//         const group = this.getGroup()
        
//         // if(isPileGroup(group)) return group.imagePiles[this.imageIndex].images
        
//         return [group.images[this.imageIndex]]
//     }
//     next() {
//         const currentGroup = this.getGroup()
//         // if (isPileGroup(currentGroup) && currentGroup.imagePiles.length > this.imageIndex + 1) {
//         //     this.imageIndex += 1
//         //     return true
//         // }
//         // else if (!isPileGroup(currentGroup) && currentGroup.images.length > this.imageIndex + 1) {
//         //     this.imageIndex += 1
//         //     return true
//         // }
//         if (this.data.order.length <= this.groupIndex) return false

//         let minDepth = Infinity
//         for(let i = this.groupIndex+1; i < this.data.order.length; i++) {
//             const group = this.data.index[this.data.order[i]]
//             if(group.closed) {
//                 if(group.depth < minDepth) {
//                     minDepth = group.depth
//                     continue
//                 }
//             }
//             if(group.depth > minDepth) continue
//             minDepth = Infinity
//             if(group.images.length == 0) continue
//             this.groupIndex = i
//             this.imageIndex = 0
//             return true
//         }
//         return false
//     }

// }

// export class GroupIterator {
//     groupIndex: number
//     data
//     constructor(data, groupIndex = 0) {
//         this.data = data
//         this.groupIndex = groupIndex
//     }

//     clone() {
//         return new GroupIterator(this.data, this.groupIndex)
//     }
//     getGroup() {
//         return this.data.index[this.data.order[this.groupIndex]]
//     }
//     next() {
//         for(let i = this.groupIndex+1; i < this.data.order.length; i++) {
//             const group = this.data.index[this.data.order[i]]
//             if(group.images.length == 0) continue
//             this.groupIndex = i
//             return true
//         }
//         return false
//     }
// }