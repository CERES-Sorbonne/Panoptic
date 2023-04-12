import { Filter, FilterOperator, Image, Images, PropertyType, PropertyValue, Property } from "@/data/models";
import { globalStore } from "@/data/store"
import { isArray } from "@vue/shared";

export const filterData = (filters: Filter[]) => {
    const images:Images = globalStore.images;
    const res = []
    for(let image of Object.values(images)){
        let keeps = []
        for(let filter of filters){
            let keep = checkIfKeepImage(image, filter)
            if(!keep && filter.strict){
                keeps = []
                break
            }
            keeps.push(keep)
        }
        if(atLeastOneTrue(keeps)){
            res.push(image)
        }
        else{
            continue
        }
    }
    return res
}

const atLeastOneTrue = (arr:boolean[]) => arr.filter(el => el).length > 0

const convertToTag = (prop:Property, tagId: number) => globalStore.tags[prop.id][tagId].value

const checkIfKeepImage = (image: Image, filter:Filter):boolean => {
    const prop = {...globalStore.properties[filter.propertyId]}
    const imageProp = {...image.properties[filter.propertyId]}
    // if no value for this prop exclude
    if(!imageProp.value){
        return false
    }
    // transform imageProp value into an array to make filtering more generalist
    if(!isArray(imageProp.value)){
        imageProp.value = [imageProp.value]
    }
    // transform ids of tags into their value to be able to compare with user value when using like
    if(prop.type === PropertyType.tag || prop.type === PropertyType.multi_tags){
        imageProp.value = imageProp.value.map((id:number) => convertToTag(prop, id))
    }


    switch(filter.operator){
        case FilterOperator.equal:
            switch(prop.type){
                default:
                    return imageProp.value.filter((el:any) => el === filter.value).length > 0
            }
        case FilterOperator.like:
            switch(prop.type){
                case PropertyType.string:
                case PropertyType.tag:
                case PropertyType.multi_tags:
                case PropertyType.url:
                case PropertyType.path:
                    return imageProp.value.filter((el:any) => el.match(filter.value)).length > 0
                default:
                    return false
            }
        case FilterOperator.geq:
        case FilterOperator.leq:
        case FilterOperator.lower:
        case FilterOperator.greater:
            switch(prop.type){
                case PropertyType.date || PropertyType.number:
                    return imageProp.value.filter((el:any) => operatorMap[filter.operator](el, filter.value)).length > 0
                default:
                    return false
            }   
        default:
            return false
    }
    return false
}

const operatorMap: {[operator in FilterOperator]? : any} = {
    [FilterOperator.geq] : (a:any,b:any) => a >= b,
    [FilterOperator.leq] : (a:any,b:any) => a <= b,
    [FilterOperator.lower] : (a:any,b:any) => a < b,
    [FilterOperator.greater] : (a:any,b:any) => a > b,
}
// pour chaque filtre
// on check toutes les propriétés de l'image
// si un filtre exclue l'image:
    // si c'est un AND
    // on vire l'image direct
    // si c'est un OR
    // on marque qu'il faut exclure l'image, et si il y a au moins un "keep" on garde