<script setup lang="ts">
import { PropertyType } from '@/data/models';
import { useStore } from '@/data/store2'
import { computed, onMounted, reactive, ref, watch } from 'vue';

import StandalonePropertyInput from '../inputs/StandalonePropertyInput.vue';
import StandaloneColorPropInput from '../inputs/StandaloneColorPropInput.vue';
import StandaloneDateInput from '../inputs/monoline/StandaloneDateInput.vue';
import StandaloneTextInput from '../inputs/multiline/StandaloneTextInput.vue';
import PropertyIcon from '../properties/PropertyIcon.vue';
import TagInputDropdown from '../tags/TagInputDropdown.vue';
import wTT from '../tooltips/withToolTip.vue'
import { isTag } from '@/utils/utils';
const store = useStore()

const props = defineProps({
    values: Object as () => { [propertyId: number]: any },
    erase: Set<number>
})
const emits = defineEmits(['blur'])

const properties = computed(() => {
    return store.propertyList.filter(p => p.id >= 0)
})

const propertyColor = computed(() => {
    const res = {} as { [pId: number]: String }
    properties.value.forEach(p => {
        if (props.erase.has(p.id)) {
            res[p.id] = 'text-warning'
            return
        }
        if (props.values[p.id] == undefined) {
            res[p.id] = 'text-secondary'
            return
        }
        res[p.id] = 'text-success'
    })
    return res
})

function test() {
    console.log('buuurr')
}

// function init() {
//     properties.value.forEach(p => {
//         if (props.values[p.id] == undefined) {
//             props.values[p.id] = propertyDefault(p.type)
//             console.log('init to', props.values[p.id])
//         }
//     })
// }

// onMounted(init)
// watch(properties, init)

</script>

<template>
    <table class="table table-sm">
        <b>{{ $t('modals.tagging.title') }}</b>
        <tbody style="border-top: 1px solid var(--border-color)">
            <tr v-for="property in properties" style="min-height: 20px;">
                <template v-if="property.id >= 0">
                    <td style="line-height: 20px;" :class="propertyColor[property.id]" class="text-nowrap">
                        <PropertyIcon :type="property.type" />
                        {{ property.name }}
                    </td>
                    <template v-if="!props.erase.has(property.id)">
                        <td class="w-100">
                            <TagInputDropdown v-if="isTag(property.type)" v-model="props.values[property.id]"
                                :property="property" :can-create="true" :auto-focus="true"
                                style="min-height: 20px; line-height: 20px;" @hide="emits('blur')" />
                            <StandaloneColorPropInput v-else-if="property.type == PropertyType.color"
                                v-model="props.values[property.id]" style="height: 20px; line-height: 20px;"
                                @blur="emits('blur')" />
                            <StandaloneTextInput
                                v-else-if="[PropertyType.string, PropertyType.number, PropertyType.url].some(t => t == property.type)"
                                :no-html="true" v-model="props.values[property.id]" :width="-1" :min-height="20"
                                :no-nl="property.type == PropertyType.number" :url-mode="property.type == PropertyType.url"
                                :only-number="property.type == PropertyType.number" @blur="emits('blur')" />
                            <StandaloneDateInput v-else-if="property.type == PropertyType.date"
                                v-model="props.values[property.id]" @blur="emits('blur')" />
                            <!-- <PropertyInput2 v-else :type="filterProperty.type" v-model="filter.value" /> -->
                            <StandalonePropertyInput v-else :type="property.type" v-model="props.values[property.id]"
                                style="height: 14px; line-height: 25px; margin-top: 4px; margin-left: 1px;" />
                        </td>
                        <td v-if="props.values[property.id] == undefined">
                            <wTT message="modals.tagging.erase_tooltip">
                                <i class="bi bi-trash base-btn" @click="erase.add(property.id)" />
                            </wTT>
                        </td>
                        <td v-else>
                            <wTT message="modals.tagging.erase_tooltip">
                                <i class="bi bi-arrow-counterclockwise base-btn"
                                    @click="delete props.values[property.id]"></i>
                            </wTT>
                        </td>
                    </template>
                    <template v-else>
                        <td class="text-warning">{{ $t("modals.tagging.erase") }}</td>
                        <td>
                            <wTT message="modals.tagging.cancel_tooltip">
                                <i class="bi bi-arrow-counterclockwise base-btn" @click="erase.delete(property.id)"></i>
                            </wTT>
                        </td>
                    </template>

                </template>
            </tr>
        </tbody>
    </table>
</template>

