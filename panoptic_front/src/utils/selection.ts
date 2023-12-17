// import { computed } from "vue";

// type Group = any
// type GroupData = any
// type ImageIterator = any
// type GroupIterator = any

// export class ImageSelector {
//     data: GroupData
//     selectedImages: Set<number>

//     lastSelectedImage: ImageIterator
//     lastSelectedGroup: GroupIterator

//     constructor(data: GroupData, selected: Set<number>) {
//         this.data = data
//         this.selectedImages = selected
//     }

//     allSelected = computed(() => this.data.root.allImageSelected)

//     clear() {
//         this.unselectGroup(this.data.root)
//         this.selectedImages.clear()
//         this.clearLastSelected()
//     }

//     selectImageIterator(iterator: ImageIterator, shift = false) {
//         if (shift) {
//             let res = this._shiftSelect(iterator)
//         }
//         this.selectImages(iterator.getImages().map(i => i.id))
//         this.clearLastSelected()
//         this.lastSelectedImage = iterator.clone()
//     }

//     unselectImageIterator(iterator: ImageIterator) {
//         this.unselectImages(iterator.getImages().map(i => i.id))
//         this.clearLastSelected()
//     }

//     toggleImageIterator(iterator: ImageIterator, shift = false) {
//         const selected = iterator.getImages().every(i => this.selectedImages.has(i.id))
//         if (selected) {
//             this.unselectImageIterator(iterator)
//         } else {
//             this.selectImageIterator(iterator, shift)
//         }
//     }
//     toggleAll() {
//         // const iterator = new GroupIterator(this.data, 0)
//         // this.toggleGroupIterator(iterator)
//     }

//     private _shiftSelect(iterator: ImageIterator) {
//         if (this.lastSelectedImage == undefined) return false

//         const lgi = this.lastSelectedImage.groupIndex
//         const igi = iterator.groupIndex
//         const lii = this.lastSelectedImage.imageIndex
//         const iii = iterator.imageIndex
//         let start = (lgi < igi || (lgi == igi && lii < iii)) ? this.lastSelectedImage : iterator
//         let end = start == this.lastSelectedImage ? iterator : this.lastSelectedImage

//         console.log(start, end)

//         let images = []
//         let it = start.clone()
//         while (it.next()) {
//             console.log(it)
//             if ((it.groupIndex >= end.groupIndex && it.imageIndex > end.imageIndex) || it.groupIndex > end.groupIndex) {
//                 break
//             }
//             images.push(...it.getImages().map(i => i.id))
//         }
//         if (images.length) {
//             this.selectImages(images)
//             return true
//         }
//         return false
//     }

//     private _shiftGroup(iterator: GroupIterator) {
//         if (this.lastSelectedGroup == undefined) return false

//         let start = this.lastSelectedGroup.groupIndex < iterator.groupIndex ? this.lastSelectedGroup : iterator
//         let end = start == iterator ? this.lastSelectedGroup : iterator
//         let images = []
//         let it = start.clone()

//         while (it.next()) {
//             if (it.groupIndex >= end.groupIndex) {
//                 break
//             }
//             const group = it.getGroup()
//             if(group.images.length) {
//                 images.push(...group.images.map(i => i.id))
//             }
//         }
//         if (images.length) {
//             this.selectImages(images)
//             return true
//         }
//         return false

//     }

//     clearLastSelected() {
//         this.lastSelectedImage = undefined
//         this.lastSelectedGroup = undefined
//     }

//     unselectImage(imageId: number) {
//         this.unselectImages([imageId])
//     }

//     selectImage(imageId: number) {
//         this.selectImages([imageId])
//     }

//     selectImages(imageIds: number[]) {
//         imageIds.forEach(id => this.selectedImages.add(id))

//         let groups = new Set<string>()
//         imageIds.forEach(id => this.data.imageToGroups[id].forEach(gId => groups.add(gId)))

//         groups.forEach(gId => this.propagateSelect(this.data.index[gId]))
//     }

//     unselectImages(imageIds: number[]) {
//         imageIds.forEach(id => this.selectedImages.delete(id))
//         let groups = new Set<string>()
//         imageIds.forEach(id => this.data.imageToGroups[id].forEach(gId => groups.add(gId)))

//         groups.forEach(gId => this.propagateUnselect(this.data.index[gId]))
//     }

//     propagateUnselect(group: Group) {
//         group.allImageSelected = false
//         if (group.parentId === undefined) return

//         this.propagateUnselect(this.data.index[group.parentId])
//     }

//     propagateSelect(group: Group) {
//         if (group.images.length) {
//             group.allImageSelected = group.images.every(i => this.selectedImages.has(i.id))
//         }
//         else {
//             group.allImageSelected = group.groups.every(g => g.allImageSelected)
//         }

//         if (group.parentId === undefined) return
//         this.propagateSelect(this.data.index[group.parentId])
//     }

//     selectGroup(group: Group) {
//         if (group.images.length > 0) {
//             this.selectImages(group.images.map(i => i.id))
//             return
//         }
//         group.groups.forEach(g => this.selectGroup(g))
//     }

//     unselectGroup(group: Group) {
//         // console.log(group)
//         if (group.images.length > 0) {
//             this.unselectImages(group.images.map(i => i.id))
//             return
//         }
//         if(group.groups) {
//             group.groups.forEach(g => this.unselectGroup(g))
//         }
//     }

//     selectGroupIterator(iterator: GroupIterator, shift = false) {
//         if (shift) {
//             this._shiftGroup(iterator)
//         }
//         this.selectGroup(iterator.getGroup())
//         this.clearLastSelected()
//         this.lastSelectedGroup = iterator.clone()
//     }

//     unselectGroupIterator(iterator: GroupIterator) {
//         this.unselectGroup(iterator.getGroup())
//         this.clearLastSelected()
//     }

//     toggleGroupIterator(iterator: GroupIterator, shift = false) {
//         const selected = iterator.getGroup().allImageSelected
//         if (selected) {
//             this.unselectGroupIterator(iterator)
//         } else {
//             this.selectGroupIterator(iterator, shift)
//         }
//     }
// }