<script setup lang="ts">
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import { Image, Property, PropertyType } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed, ref } from 'vue';
import TextPropInput from '../TextPropInput.vue';
import { keyState } from '@/data/keyState';

const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Image,
    width: Number,
    height: Number,
    noNl: Boolean
})

const dropdownElem = ref(null)
const isHover = ref(false)

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))
const minWidth = computed(() => Math.max(props.width + 1, 100))
const urlMode = computed(() => props.property.type == PropertyType.url && keyState.alt && isHover.value)

function contentClick(e) {
    if (urlMode.value && keyState.alt && propRef.value?.value) {
        let url = propRef.value?.value as string
        if(!url.startsWith('http')) {
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
                <span v-if="propRef.value" @click="contentClick">{{ propRef.value }}</span>
                <span v-else class="text-secondary">None...</span>
            </div>
        </template>
        <template v-slot:popup>
            <div class="w-100 " style="font-size: 12px; line-height: 22px;">
                <TextPropInput :image="props.image" :property="props.property" :auto-focus="true" :min-height="28"
                    :width="minWidth" :always-shadow="true" :no-nl="props.noNl" @save="dropdownElem.hide()" :blur-on-enter="true" />
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