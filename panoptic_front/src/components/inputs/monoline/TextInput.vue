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

const widthGoal = ref(0)
const propValue = computed(() => data.instances[props.image.id].properties[props.property.id])
const minWidth = computed(() => Math.max(props.width + 1, widthGoal.value))
const urlMode = computed(() => props.property.type == PropertyType.url && keyState.ctrl && isHover.value)

function contentClick(e) {
    if (urlMode.value && keyState.ctrl && propValue.value) {
        e.preventDefault()
        let url = propValue.value as string
        if (!url.startsWith('http')) {
            url = 'http://' + url
        }
        window.open(url, '_blank').focus()
        e.preventDefault()
        e.stopPropagation()
    }
}

function computeSize() {
    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext("2d");
    ctx.font = "11px Arial";
    var length = ctx.measureText(propValue.value).width;
    widthGoal.value = 0
    if (length > 500) {
        widthGoal.value = 200
    }
    if (length > 800) {
        widthGoal.value = 300
    }
    if (length > 1000) {
        widthGoal.value = 400
    }
}

</script>

<template>
    <Dropdown :offset="-24" :no-shadow="true" ref="dropdownElem" :teleport="true" @show="computeSize">
        <template v-slot:button>
            <div class="btn-class text-truncate" @mouseenter="isHover = true" @mouseleave="isHover = false"
                :style="{ width: props.width + 'px', height: props.height + 'px', lineHeight: props.height + 'px', color: (urlMode ? 'blue' : 'inherit') }">
                <span v-if="propValue != undefined" @click="contentClick">{{ propValue }}</span>
                <span v-else class="text-secondary">None...</span>
            </div>
        </template>
        <template v-slot:popup>
            <div class="w-100" style="font-size: 12px; line-height: 22px;">
                <TextPropInput :image="props.image" :property="props.property" :auto-focus="true" :min-height="24"
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