<script setup lang="ts">
import { Colors, DateUnit, PropertyType, PropertyValue, Tag } from '@/data/models';
import { computed } from 'vue';
import TagBadge from '../tagtree/TagBadge.vue';
import { UNDEFINED_KEY } from '@/core/GroupManager';
import { useProjectStore } from '@/data/projectStore';
import { pad } from '@/utils/utils'
import { useDataStore } from '@/data/dataStore';

const data = useDataStore()
const store = useProjectStore()

const props = defineProps({
    value: Object as () => PropertyValue
})

const property = computed(() => data.properties[props.value.propertyId])
const type = computed(() => property.value.type)

const isTag = computed(() => type.value == PropertyType.tag || type.value == PropertyType.multi_tags)


const color = computed(() => {
    if (props.value.value == undefined) return 'white'

    let value = Number(props.value.value)
    if (isNaN(value) || value > 12) return 'gray'
    return Colors[value].color
})

const date = computed(() => {
    if (property.value.type != PropertyType.date) return
    let unit = props.value.unit

    const d = props.value.value as Date
    const units = [DateUnit.Year, DateUnit.Month, DateUnit.Day, DateUnit.Hour, DateUnit.Minute]
    let res = ''
    res += d.getUTCFullYear()
    if (unit == DateUnit.Year) return res
    res += '/'
    res += (pad(d.getUTCMonth() + 1))
    if (unit == DateUnit.Month) return res
    res += '/'
    res += pad(d.getUTCDate())
    if (unit == DateUnit.Week) return res
    if (unit == DateUnit.Day) return res
    res += ' '
    res += pad(d.getUTCHours())
    if (unit == DateUnit.Hour) return res + 'h'
    res += ':'
    res += pad(d.getUTCMinutes())
    return res
})

const dateEnd = computed(() => {
    if (property.value.type != PropertyType.date) return
    if (!props.value.valueEnd) return

    const d = props.value.valueEnd as Date
    const units = [DateUnit.Year, DateUnit.Month, DateUnit.Day, DateUnit.Hour, DateUnit.Minute]
    let res = ''
    res += d.getUTCFullYear()
    if (props.value.unit == DateUnit.Year) return res
    res += '/'
    res += (pad(d.getUTCMonth() + 1))
    if (props.value.unit == DateUnit.Month) return res
    res += '/'
    res += pad(d.getUTCDate())
    if (props.value.unit == DateUnit.Week) return res
    if (props.value.unit == DateUnit.Day) return res
    res += ' '
    res += pad(d.getUTCHours())
    if (props.value.unit == DateUnit.Hour) return res + 'h'
    res += ':'
    res += pad(d.getUTCMinutes())
    return res
})

function mapTag(id: number | string): Tag[] {
    // console.log(id)
    if (id == undefined) {
        return [{ value: '_indéfini', color: -1 } as Tag]
    }
    return [data.properties[props.value.propertyId].tags[id as number]]
}
</script>

<template>
    <div class="d-flex text-nowrap p-0 m-0" v-if="property">
        <div class="me-2">{{ property.name }}: </div>
        <div v-if="property.type == PropertyType.color" :style="{ backgroundColor: color }" class="color-holder">
        </div>
        <div v-else-if="property.type == PropertyType._folders">
            <TagBadge :tag="store.data.folders[props.value.value].name" :color="-1" />
        </div>
        <span v-else-if="property.type == PropertyType.date && props.value.value">
            {{ date }}
            <span class="ms-1 me-1">to</span>
            {{ dateEnd }}
        </span>
        <span v-else-if="property.type == PropertyType.date"> undefined </span>
        <span v-else-if="!isTag">
            <span v-if="props.value.value != UNDEFINED_KEY">{{ props.value.value }}</span>
            <span v-else class="text-secondary">indéfini</span>
        </span>
        <span v-else>
            <span v-for="tag in mapTag(props.value.value)">
                <TagBadge :tag="tag.value" :color="tag.color" />
            </span>
        </span>
    </div>
</template>

<style scoped>
.color-holder {
    margin-top: 6px;
    height: 15px;
    width: 15px;
    border: 1px solid var(--border-color);
    border-radius: 5px;
}
</style>