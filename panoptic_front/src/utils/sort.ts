import { Image, Property, PropertyType } from "@/data/models";
import { globalStore } from "@/data/store";

function getSortFunction(type: PropertyType) {
    switch(type) {
        case PropertyType.string:
        case PropertyType.url:
        case PropertyType.number:
        case PropertyType.path:
        case PropertyType.sha1:
        case PropertyType.ahash:
        case PropertyType.color:
        case PropertyType.date:
            return (a:any,b:any) => {
                if(a == undefined || a == '') return 1
                if(b == undefined || b == '') return -1
                return a < b ? -1 : a > b ? 1 : 0
            }
        case PropertyType.checkbox:
            return (a:any, b:any) => {
                if(a) {
                    return -1
                }
                if(a == b) {
                    return 0
                }
                return 1
            }
        case PropertyType.multi_tags:
            return (a:Array<string>, b:Array<string>) => {
                let al = Array.isArray(a) ? a.length : 0
                let bl = Array.isArray(b) ? b.length : 0
                return al - bl
            }
        case PropertyType.tag:
            return (a:string, b:string) => {
                if(a == undefined) return -1
                if(b == undefined) return 1
                return a < b ? -1 : a > b ? 1 : 0
            }
        default:
            return () => -1
    }
}

function getImageSortFunction(property: Property) {
    function sortImages(img1: Image, img2: Image) {
        let p1 = img1.properties[property.id]?.value
        let p2 = img2.properties[property.id]?.value

        if(property.type == PropertyType.tag) {
            let t1 = Array.isArray(p1) && p1.length > 0 ? p1[0] : undefined
            let t2 = Array.isArray(p2) && p2.length > 0 ? p2[0] : undefined

            p1 = globalStore.tags[property.id][t1]?.value
            p2 = globalStore.tags[property.id][t2]?.value
        }

        let sortFnc = getSortFunction(property.type)
        return sortFnc(p1, p2)
    }
    return sortImages
}

export function sortImages(images: Array<Image>, property: Property) {
    let fnc = getImageSortFunction(property)
    images.sort(fnc)
    return images
}