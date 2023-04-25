import { Filter, FilterOperator, Image, FilterGroup, PropertyType } from "@/data/models";
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
            filter = filter as Filter
            let property = image.properties[filter.propertyId]
            let propertyValue = property ? property.value : undefined
            let subRes = computeFilter(filter, propertyValue)
            res = groupOperatorFnc(res, subRes)
            // console.log('subRes : ' + subRes + '  >> ' + res)
        }
    }
    return res
}