import { Filter, FilterOperator, Image, FilterGroup, PropertyType, Tag, AFilter } from "@/data/models";
import { globalStore } from "@/data/store";
import { isArray } from "@vue/shared";
import { reactive } from "vue";


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

function isEmpty(value: any) {
    return value === undefined || value === '' || (isArray(value) && value.length === 0)
}

const operatorMap: { [operator in FilterOperator]?: any } = {
    [FilterOperator.geq]: (a: any, b: any) => {
        if (b == undefined) return true;
        if (a == undefined) return false;
        return a >= b
    },
    [FilterOperator.leq]: (a: any, b: any) => {
        if (b == undefined) return true;
        if (a == undefined) return false;
        return a <= b
    },
    [FilterOperator.lower]: (a: any, b: any) => {
        if (b == undefined) return true;
        if (a == undefined) return false;
        return a < b
    },
    [FilterOperator.greater]: (a: any, b: any) => {
        if (b == undefined) return true;
        if (a == undefined) return false;
        return a > b
    },
    [FilterOperator.and]: (a: boolean, b: boolean) => a && b,
    [FilterOperator.or]: (a: boolean, b: boolean) => a || b,
    [FilterOperator.contains]: (a: string, b: string) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        return a.includes(b)
    },
    [FilterOperator.containsAll]: (a: any[], b: any[]) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        return b.filter(e => a.includes(e)).length == b.length
    },
    [FilterOperator.containsAny]: (a: any[], b: any[]) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        return a.some(e => b.includes(e))
    },
    [FilterOperator.containsNot]: (a: any[], b: any[]) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return true;
        return !a.some(e => b.includes(e))
    },
    [FilterOperator.equal]: (a: any, b: any) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        return a == b
    },
    [FilterOperator.equalNot]: (a: any, b: any) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return true;
        return a != b
    },
    [FilterOperator.isFalse]: (a: any) => {
        if (isEmpty(a)) return true;
        return a == false
    },
    [FilterOperator.isTrue]: (a: any) => a,
    [FilterOperator.isSet]: (a: any) => !isEmpty(a),
    [FilterOperator.notSet]: (a: any) => isEmpty(a),
    [FilterOperator.startsWith]: (a: string, b: string) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
        return a.startsWith(b)
    },
    [FilterOperator.like]: (a: string, b: string) => {
        if (isEmpty(b)) return true;
        if (isEmpty(a)) return false;
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
    if (filterGroup.filters.length == 0) {
        return true
    }

    let groupOp = filterGroup.groupOperator ? filterGroup.groupOperator : FilterOperator.and
    let res = groupOp == FilterOperator.and ? true : false
    let groupOperatorFnc = operatorMap[groupOp]

    // console.log(groupOp)

    for (let filter of filterGroup.filters) {
        // console.log('resssss ' + res)
        if (filter.isGroup) {
            // console.log('subgroup')
            res = groupOperatorFnc(computeGroupFilter(image, filter), res)
        }
        else {
            let nfilter = { ...filter } as Filter
            let propId = nfilter.propertyId
            let propType = globalStore.properties[propId].type

            let property = image.properties[propId]
            let propertyValue = property ? property.value : undefined

            if (Array.isArray(nfilter.value) && nfilter.value.length > 0 && (propType == PropertyType.tag || propType == PropertyType.multi_tags)) {
                let filterValue = nfilter.value as number[]
                // console.log(filterValue)
                let tags = globalStore.tagNodes[propId]
                let found = {} as any
                let toCheck = [] as number[]
                filterValue.forEach((v: number) => toCheck.push(v))
                while (toCheck.length > 0) {
                    let id = toCheck.splice(0, 1)[0]
                    if (found[id]) {
                        continue
                    }
                    found[id] = true
                    let tag = tags[id]
                    if (tag && tag.children != undefined) {
                        Object.values(tag.children).forEach((c: any) => { toCheck.push(c.id) })
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


export class FilterManager {
    filter: FilterGroup
    filterIndex: { [filterId: number]: AFilter }

    constructor(filter: FilterGroup = undefined) {
        this.filter = filter
        this.filterIndex = {}
        if (this.filter == undefined) {
            this.filterIndex = {}
            this.addNewFilterGroup()
        } else {
            this.recursiveRegister(this.filter)
        }

    }

    addNewFilterGroup(parentId: number = undefined) {
        let group = this.createFilterGroup()


        if (parentId != undefined) {
            let parent = this.filterIndex[parentId] as FilterGroup
            if (parent == undefined) throw 'Invalid Parent !'
            parent.filters.push(group)
            const reactiveGroup = parent.filters[parent.filters.length - 1]
            this.registerFilter(reactiveGroup)
            return reactiveGroup
        }

        if (this.filter == undefined) {
            this.filter = reactive(group)
            this.registerFilter(this.filter)
            return this.filter
        }

        this.filter.filters.push(group)
        const reactiveGroup = this.filter.filters[this.filter.filters.length - 1]
        this.registerFilter(reactiveGroup)
        return reactiveGroup
    }

    addNewFilter(propertyId: number, parentId: number = undefined) {
        let filter = this.createFilter(propertyId)

        if (parentId != undefined) {
            let group = this.filterIndex[parentId] as FilterGroup
            if (group == undefined) throw new Error('group is undefined')
            if (!group.isGroup) throw new TypeError('Parent filter is not a FilterGroup, cannot add filter to it')
            group.filters.push(filter)
            const reactiveFilter = group.filters[group.filters.length-1]
            this.registerFilter(reactiveFilter)
            return reactiveFilter
        }

        this.filter.filters.push(filter)
        // get the reactive version
        const reactiveFilter = this.filter.filters[this.filter.filters.length-1]
        this.registerFilter(reactiveFilter)
        return reactiveFilter
    }

    deleteFilter(filterId: number) {
        Object.values(this.filterIndex).forEach(f => {
            if(!f.isGroup) return
            const group = f as FilterGroup
            group.filters = group.filters.filter(f => f.id != filterId)
        })

        delete this.filterIndex[filterId]
    }

    private registerFilter(filter: AFilter) {
        if(filter.id >= 0) {
            console.error('registerFilter should not receive a filter with valid id')
        }
        filter.id = this.nextIndex()
        this.filterIndex[filter.id] = filter
        return this.filterIndex[filter.id]
    }

    private createFilter(propertyId: number) {
        let property = globalStore.properties[propertyId]

        let filter: Filter = {
            propertyId: property.id,
            operator: defaultOperator(property.type),
            value: undefined,
            id: -1
        }
        return filter
    }

    private createFilterGroup() {
        let filter: FilterGroup = {
            filters: [],
            groupOperator: FilterOperator.or,
            depth: 0,
            isGroup: true,
            id: -1
        }
        return filter
    }

    private nextIndex() {
        if (this.filter == undefined || Object.keys(this.filterIndex).length == 0) {
            return 0
        }
        return Math.max(...Object.keys(this.filterIndex).map(Number)) + 1
    }

    private recursiveRegister(filter: AFilter) {
        if(filter.id == undefined || filter.id == -1){
            filter = this.registerFilter(filter)
        } else {
            this.filterIndex[filter.id] = filter
        }
        
        if(!filter.isGroup) return

        const group = filter as FilterGroup
        group.filters.forEach(g => this.recursiveRegister(g))
    }
}