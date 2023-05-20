import { Filter, FilterOperator, Image, FilterGroup, PropertyType, Tag } from "@/data/models";
import { globalStore } from "@/data/store";
import { isArray } from "@vue/shared";


export function defaultOperator(propertyType: PropertyType) {
    switch (propertyType) {
        case PropertyType.checkbox:
            return FilterOperator.isTrue

        case PropertyType.multi_tags:
        case PropertyType.tag:
            return FilterOperator.containsAny

        case PropertyType.date:
            return FilterOperator.greater

        default:
            return FilterOperator.equal
    }
}

function isEmpty(value:any) {
    return value == undefined || value == '' || (isArray(value) && value.length == 0)
}

const operatorMap: {[operator in FilterOperator]? : any} = {
    [FilterOperator.geq] : (a:any,b:any) => {
        if(b == undefined) return true;
        if(a == undefined) return false;
        return a >= b
    },
    [FilterOperator.leq] : (a:any,b:any) => {
        if(b == undefined) return true;
        if(a == undefined) return false;
        return a <= b
    },
    [FilterOperator.lower] : (a:any,b:any) => {
        if(b == undefined) return true;
        if(a == undefined) return false;
        return a < b
    },
    [FilterOperator.greater] : (a:any,b:any) => {
        if(b == undefined) return true;
        if(a == undefined) return false;
        return a > b
    },
    [FilterOperator.and] : (a: boolean, b: boolean) => a && b,
    [FilterOperator.or] : (a: boolean, b: boolean) => a || b,
    [FilterOperator.contains] : (a: string, b: string) => {
        if(isEmpty(b)) return true;
        if(isEmpty(a)) return false;
        return a.includes(b)
    },
    [FilterOperator.containsAll] : (a: any[], b: any[]) => {
        if(isEmpty(b)) return true;
        if(isEmpty(a)) return false;
        return b.filter(e => a.includes(e)).length == b.length
    },
    [FilterOperator.containsAny] : (a: any[], b: any[]) => {
        if(isEmpty(b)) return true;
        if(isEmpty(a)) return false;
        return a.some(e => b.includes(e))
    },
    [FilterOperator.containsNot] : (a: any[], b: any[]) => {
        if(isEmpty(b)) return true;
        if(isEmpty(a)) return true;
        return !a.some(e => b.includes(e))
    },
    [FilterOperator.equal] : (a: any, b: any) => {
        if(isEmpty(b)) return true;
        if(isEmpty(a)) return false;
        return a == b
    },
    [FilterOperator.equalNot] : (a: any, b: any) => {
        if(isEmpty(b)) return true;
        if(isEmpty(a)) return true;
        return a != b
    },
    [FilterOperator.isFalse] : (a: any) => {
        if(isEmpty(a)) return true;
        return a == false
    },
    [FilterOperator.isTrue] : (a: any) => a,
    [FilterOperator.isSet] : (a: any) => !isEmpty(a),
    [FilterOperator.notSet] : (a: any) => isEmpty(a),
    [FilterOperator.startsWith] : (a: string, b:string) => {
        if(isEmpty(b)) return true;
        if(isEmpty(a)) return false;
        return a.startsWith(b)
    },
    [FilterOperator.like] : (a: string, b:string) => {
        if(isEmpty(b)) return true;
        if(isEmpty(a)) return false;
        return a.match(b)
    }

}


function computeFilter(filter: Filter, propertyValue: any) {
    // console.log(filter.value)
    let opFnc = operatorMap[filter.operator]
    let res = opFnc(propertyValue, filter.value)
    return res
}

export function computeGroupFilter(image: Image, filterGroup: FilterGroup) {
    // console.log('filter: ' + image.sha1)
    if(filterGroup.filters.length == 0) {
        return true
    }

    let groupOp = filterGroup.groupOperator ? filterGroup.groupOperator : FilterOperator.and
    let res = groupOp == FilterOperator.and ? true : false
    let groupOperatorFnc = operatorMap[groupOp]

    // console.log(groupOp)

    for(let filter of filterGroup.filters) {
        // console.log('resssss ' + res)
        if(filter.isGroup) {
            // console.log('subgroup')
            res = groupOperatorFnc(computeGroupFilter(image, filter), res)
        }
        else {
            let nfilter = {...filter} as Filter
            let propId = nfilter.propertyId
            let propType = globalStore.properties[propId].type

            let property = image.properties[propId]
            let propertyValue = property ? property.value : undefined

            if(Array.isArray(nfilter.value) && nfilter.value.length > 0 && (propType == PropertyType.tag || propType == PropertyType.multi_tags)) {
                let filterValue = nfilter.value as number[]
                // console.log(filterValue)
                let tags = globalStore.tagNodes[propId]
                let found = {} as any
                let toCheck = [] as number[]
                filterValue.forEach((v:number) => toCheck.push(v))
                while(toCheck.length > 0) {
                    let id = toCheck.splice(0,1)[0]
                    if(found[id]) {
                        continue
                    }
                    found[id] = true
                    let tag = tags[id]
                    if(tag && tag.children != undefined) {
                        Object.values(tag.children).forEach((c: any) => {toCheck.push(c.id)})
                    }
                }

                filterValue = Object.keys(found).map(Number)
                // console.log('updated to: ' + filterValue)
                nfilter.value = filterValue
            }

            let subRes = computeFilter(nfilter, propertyValue)
            res = groupOperatorFnc(res, subRes)
            // console.log('subRes : ' + subRes + '  >> ' + res)
        }
    }
    return res
}