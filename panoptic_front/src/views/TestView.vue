<script setup lang="ts">
import ColorPropInputNoDropdown from '@/components/inputs/ColorPropInputNoDropdown.vue';
import ContentEditable from '@/components/inputs2/utils/ContentEditable.vue';
import ColorInput from '@/components/property_inputs/ColorInput.vue';
import DateInput from '@/components/property_inputs/DateInput.vue';
import NumberInput from '@/components/property_inputs/NumberInput.vue';
import TextInput from '@/components/property_inputs/TextInput.vue';
import ColorPreview from '@/components/property_preview/ColorPreview.vue';
import DatePreview from '@/components/property_preview/DatePreview.vue';
import NumberPreview from '@/components/property_preview/NumberPreview.vue';
import TextPreview from '@/components/property_preview/TextPreview.vue';
import UrlPreview from '@/components/property_preview/UrlPreview.vue';
import { keyState } from '@/data/keyState';
import { onMounted, ref } from 'vue';


const text = ref('Lorem Ipsum is simply dummy text \n \nof the printing and typesetting industry.')
const url = ref('google.com')
const number = ref(12.3)
const color = ref(0)
const elem2 = ref(null)
function simulateClick() {
    elem2.value.forceFocus()
}

const date = ref("2024-04-04T23:26:00Z")

onMounted(() => {
    let isMac = true
    window.addEventListener('keydown', (ev) => {
        if (ev.key == 'Control') keyState.ctrl = true;
        if (ev.key == 'Alt') {
            if (isMac) {
                keyState.ctrl = true
            }
            keyState.alt = true;
        }
        if (ev.key == 'Shift') keyState.shift = true;
        if (ev.key == 'ArrowLeft') keyState.left = true;
        if (ev.key == 'ArrowRight') { keyState.right = true; console.log('keeeyy') }

        // if (ev.key == 'Z' && keyState.ctrl) data.redo()
        // if (ev.key == 'z' && keyState.ctrl) data.undo()
    })
    window.addEventListener('keyup', (ev) => {
        if (ev.key == 'Control') keyState.ctrl = false;
        if (ev.key == 'Alt') {
            if (isMac) {
                keyState.ctrl = false
            }
            keyState.alt = false;
        }
        if (ev.key == 'Shift') keyState.shift = false;
        if (ev.key == 'ArrowLeft') keyState.left = false;
        if (ev.key == 'ArrowRight') keyState.right = false;
    })
    window.addEventListener('mousemove', (ev) => {
        keyState.ctrl = ev.ctrlKey
        keyState.alt = ev.altKey
        keyState.shift = ev.shiftKey
        if (isMac) {
            keyState.ctrl = keyState.ctrl || keyState.alt
        }
    })
})

</script>

<template>
    <div class="d-flex flex-wrap p-2">
        <div class="item border rounded">
            <h5 class="text-secondary">Date</h5>
            <span class="text-secondary">Preview</span>
            <div class="mb-1">
                <DatePreview :date="date" />
            </div>
            <span class="text-secondary">Input</span>
            <div>
                <DateInput v-model="date" />
            </div>
        </div>

        <div class="item border rounded">
            <h5 class="text-secondary">Text</h5>
            <span class="text-secondary">Preview</span>
            <div class="mb-1">
                 <TextPreview :text="text" />
            </div>
            <span class="text-secondary">Input</span>
            <div>
                <TextInput v-model="text" />
            </div>
        </div>

        <div class="item border rounded">
            <h5 class="text-secondary">Url</h5>
            <span class="text-secondary">Preview</span>
            <div class="mb-1">
                 <UrlPreview :url="url" />
            </div>
            <span class="text-secondary">Input</span>
            <div>
                <TextInput v-model="url" :url-mode="true"/>
            </div>
        </div>

        <div class="item border rounded">
            <h5 class="text-secondary">Number</h5>
            <span class="text-secondary">Preview</span>
            <div class="mb-1">
                 <NumberPreview :number="number" />
            </div>
            <span class="text-secondary">Input</span>
            <div>
                <NumberInput v-model="number" />
            </div>
        </div>

        <div class="item border rounded">
            <h5 class="text-secondary">Color</h5>
            <span class="text-secondary">Preview</span>
            <div class="mb-1">
                 <ColorPreview :color="color" />
            </div>
            <span class="text-secondary">Input</span>
            <div>
                <ColorInput v-model="color"/>
            </div>
        </div>

        <!-- <br />

        <DatePreview :date="undefined" />
        <div>{{ text }}</div>
        <div style="width: 300px; height: 200px; background-color: bisque;" class="overflow-auto">
            <ContentEditable v-model="text" class="h-100 w-100 test" />
        </div>
        <br />
        {{ number }}
        <div style="width: 300px; height: 200px; background-color: bisque;" class="overflow-auto">
            <ContentEditable v-model="number" :only-number="true" class="h-100 w-100" />
        </div>
        <br />
        {{ color }}
        <div style="width: 300px; height: 200px; background-color: bisque;" class="overflow-auto">
            <ColorPropInputNoDropdown v-model="color" />
        </div> -->

    </div>
</template>

<style scoped>
.test:focus {
    background-color: blueviolet !important;
}

.item {
    width: 250px;
    padding: 5px;
    margin-right: 10px;
    margin-bottom: 10px;
}
</style>