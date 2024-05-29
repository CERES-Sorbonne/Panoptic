<script setup lang="ts">
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import { Instance, Property, PropertyType } from '@/data/models';
import { computed, ref } from 'vue';
import TextPropInput from '../TextPropInput.vue';
import { keyState } from '@/data/keyState';
import { useDataStore } from '@/data/dataStore';


const data = useDataStore()

const props = defineProps<{
    property: Property,
    image: Instance
    width: number
    height: number
    noNl?: boolean
}>()

const dropdownElem = ref(null)
const isHover = ref(false)


const propValue = computed(() => data.instances[props.image.id].properties[props.property.id])
const minWidth = computed(() => Math.max(props.width + 1, 100))
const urlMode = computed(() => props.property.type == PropertyType.url && keyState.alt && isHover.value)

function contentClick(e) {
    if (urlMode.value && keyState.alt && propValue.value) {
        let url = propValue.value as string
        if (!url.startsWith('http')) {
            url = 'http://' + url
        }
        window.open(url, '_blank').focus()
        e.preventDefault()
        e.stopPropagation()
    }
}

</script>

<template>
    <Dropdown :offset="-24" :no-shadow="true" ref="dropdownElem" :teleport="true">
        <template v-slot:button>
            <div class="btn-class" @mouseenter="isHover = true" @mouseleave="isHover = false"
                :style="{ width: props.width + 'px', height: props.height + 'px', lineHeight: props.height + 'px', color: (urlMode ? 'blue' : 'inherit') }">
                <span v-if="propValue != undefined" @click="contentClick">{{ propValue }}</span>
                <span v-else class="text-secondary">None...</span>
            </div>
        </template>
        <template v-slot:popup>
            <div class="w-100 " style="font-size: 12px; line-height: 22px;">
                <TextPropInput :image="props.image" :property="props.property" :auto-focus="true" :min-height="28"
                    :width="minWidth" :always-shadow="true" :no-nl="props.noNl" @save="dropdownElem.hide()"
                    :blur-on-enter="true" />
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.btn-class {
    font-size: 12px;
    text-overflow: ellipsis;
    overflow: hidden;
    cursor: pointer;
}
</style>