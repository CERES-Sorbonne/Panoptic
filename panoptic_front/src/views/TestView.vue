<script setup lang="ts">
import ContentEditable from '@/components/inputs2/utils/ContentEditable.vue';
import { ref } from 'vue';


const text = ref('test')
const number = ref('12.3')
const elem2 = ref(null)

function simulateClick() {
    elem2.value.forceFocus()
}

</script>

<template>
    <div>
        <div>{{ text }}</div>
        <div style="width: 300px; height: 200px; background-color: bisque;" class="overflow-scroll">
            <ContentEditable v-model="text" class="h-100 w-100"/>
        </div>
        <br />
        {{ Number(number) }}
        <div style="width: 300px; height: 200px; background-color: bisque;" class="overflow-scroll">
            <ContentEditable v-model="number" :only-number="true" class="h-100 w-100"/>
        </div>
    </div>
</template>

<style scoped></style>