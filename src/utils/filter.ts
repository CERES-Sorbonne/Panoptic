import { Filter, FilterOperator, Image, FilterGroup } from "@/data/models";
import { isArray } from "@vue/shared";


const operatorMap: {[operator in FilterOperator]? : any} = {
    [FilterOperator.geq] : (a:any,b:any) => a >= b,
    [FilterOperator.leq] : (a:any,b:any) => a <= b,
    [FilterOperator.lower] : (a:any,b:any) => a < b,
    [FilterOperator.greater] : (a:any,b:any) => a > b,
    [FilterOperator.and] : (a: boolean, b: boolean) => a && b,
    [FilterOperator.or] : (a: boolean, b: boolean) => a || b,
    [FilterOperator.contains] : (a: string, b: string) => a.includes(b),
    [FilterOperator.containsAll] : (a: any[], b: any[]) => b.filter(e => a.includes(e)).length == b.length,
    [FilterOperator.containsAny] : (a: any[], b: any[]) => a.some(e => b.includes(e)),
    [FilterOperator.containsNot] : (a: any[], b: any[]) => !a.some(e => b.includes(e)),
    [FilterOperator.equal] : (a: any, b: any) => a == b,
    [FilterOperator.equalNot] : (a: any, b: any) => a != b,
    [FilterOperator.isFalse] : (a: any) => a == false,
    [FilterOperator.isTrue] : (a: any) => a,
    [FilterOperator.isSet] : (a: any) => a != undefined && a != '' && (!isArray(a) || a.length > 0),
    [FilterOperator.notSet] : (a: any) => a == undefined || a == '' || (isArray(a) && a.length == 0),
    [FilterOperator.startsWith] : (a: string, b:string) => a.startsWith(b),
    [FilterOperator.like] : (a: string, b:string) => a.startsWith(b)

}


function computeFilter(filter: Filter, propertyValue: any) {
    // console.log('filter ' + filter.value + ' -- ' + propertyValue)
    if(propertyValue == undefined || (isArray(propertyValue) && propertyValue.length == 0)) {
        switch(filter.operator) {
            case FilterOperator.geq:
            case FilterOperator.leq:
            case FilterOperator.lower:
            case FilterOperator.greater:
            case FilterOperator.contains:
            case FilterOperator.containsAll:
            case FilterOperator.containsAny:
            case FilterOperator.equal:
            case FilterOperator.equalNot:
            case FilterOperator.isTrue:
            case FilterOperator.isSet:
            case FilterOperator.startsWith:
            case FilterOperator.like:
                return false
            case FilterOperator.containsNot:
            case FilterOperator.notSet:
            case FilterOperator.isFalse:
                return true
        }
    }

    if(filter.value == undefined || (isArray(filter.value) && filter.value.length == 0)) {
        switch(filter.operator) {
            case FilterOperator.geq:
            case FilterOperator.leq:
            case FilterOperator.lower:
            case FilterOperator.greater:
            case FilterOperator.contains:
            case FilterOperator.containsAll:
            case FilterOperator.containsAny:
            case FilterOperator.equal:
            case FilterOperator.equalNot:
            case FilterOperator.isTrue:
            case FilterOperator.isSet:
            case FilterOperator.startsWith:
            case FilterOperator.like:
                case FilterOperator.containsNot:
                return true
        }
    }

    let opFnc = operatorMap[filter.operator]
    let res = opFnc(propertyValue, filter.value)
    // console.log('filter res: ' + res)
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