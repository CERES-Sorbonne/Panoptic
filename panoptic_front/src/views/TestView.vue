<script setup lang="ts">
import ColorPropInputNoDropdown from '@/components/inputs/ColorPropInputNoDropdown.vue';
import ContentEditable from '@/components/inputs2/utils/ContentEditable.vue';
import DateInput from '@/components/property_inputs/DateInput.vue';
import DatePreview from '@/components/property_preview/DatePreview.vue';
import { ref } from 'vue';


const text = ref('test')
const number = ref('12.3')
const color = ref(0)
const elem2 = ref(null)
function simulateClick() {
    elem2.value.forceFocus()
}

const date = ref("2024-04-04T23:26:00Z")

</script>

<template>
    <div>
        <DateInput v-model="date"/>
        <br />
        <DatePreview :date="date" />
        <DatePreview :date="undefined" />
        <div>{{ text }}</div>
        <div style="width: 300px; height: 200px; background-color: bisque;" class="overflow-auto">
            <ContentEditable v-model="text" class="h-100 w-100 test"/>
        </div>
        <br />
        {{ number }}
        <div style="width: 300px; height: 200px; background-color: bisque;" class="overflow-auto">
            <ContentEditable v-model="number" :only-number="true" class="h-100 w-100"/>
        </div>
        <br />
        {{ color }}
        <div style="width: 300px; height: 200px; background-color: bisque;" class="overflow-auto">
            <ColorPropInputNoDropdown v-model="color" />
        </div>


    </div>
</template>

<style scoped>

.test:focus {
    background-color: blueviolet !important;
}

</style>