<script setup lang="ts">
import Dropdown from '@/components/dropdowns/Dropdown.vue';
import { Image, Property } from '@/data/models';
import { getImageProperty } from '@/utils/utils';
import { computed, ref } from 'vue';
import TextPropInput from '../TextPropInput.vue';

const props = defineProps({
    property: Object as () => Property,
    image: Object as () => Image,
    width: Number,
    height: Number,
    noNl: Boolean
})

const dropdownElem = ref(null)

const propRef = computed(() => getImageProperty(props.image.id, props.property.id))
const minWidth = computed(() => Math.max(props.width + 1, 100))

</script>

<template>
    <Dropdown :offset="'-2,-24'" :no-shadow="true" ref="dropdownElem">
        <template v-slot:button>
            <div class="btn-class"
                :style="{ width: props.width + 'px', height: props.height + 'px', lineHeight: props.height + 'px' }">
                <span v-if="propRef.value">{{ propRef.value }}</span>
                <span v-else class="text-secondary">None...</span>
            </div>
        </template>
        <template v-slot:popup>
            <div class="w-100 " style="font-size: 12px; line-height: 22px;">
                <TextPropInput :image="props.image" :property="props.property" :auto-focus="true" :min-height="28"
                    :width="minWidth" :always-shadow="true" :no-nl="props.noNl" />
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