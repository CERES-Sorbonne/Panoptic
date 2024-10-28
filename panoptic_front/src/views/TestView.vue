<script setup lang="ts">

import CellColorInput from '@/components/property_cell_input/CellColorInput.vue';
import CheckboxInput from '@/components/property_inputs/CheckboxInput.vue';
import DateInput from '@/components/property_inputs/DateInput.vue';
import DBInput from '@/components/property_inputs/DBInput.vue';
import NumberInput from '@/components/property_inputs/NumberInput.vue';
import TagInput from '@/components/property_inputs/TagInput.vue';
import TextInput from '@/components/property_inputs/TextInput.vue';
import DatePreview from '@/components/property_preview/DatePreview.vue';
import NumberPreview from '@/components/property_preview/NumberPreview.vue';
import TextPreview from '@/components/property_preview/TextPreview.vue';
import UrlPreview from '@/components/property_preview/UrlPreview.vue';
import RowDateInput from '@/components/property_row_input/RowDateInput.vue';
import RowTextInput from '@/components/property_row_input/RowTextInput.vue';
import TagInputDropdown from '@/components/tags/TagInputDropdown.vue';
import { useDataStore } from '@/data/dataStore';
import { keyState } from '@/data/keyState';
import { PropertyType } from '@/data/models';
import { computed, onMounted, ref } from 'vue';

const data = useDataStore()

const text = ref('Lorem Ipsum is simply dummy text \n \nof the printing and typesetting industry.')
const url = ref('google.com')
const number = ref(12.3)
const color = ref(0)
const checkbox = ref(true)
const date = ref("2024-04-04T23:26:00Z")
const tags = ref([])

const instance = computed(() => data.instances[1])
const property = computed(() => data.properties[3])

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
    <div v-if="data.propertyList.length" class="d-flex flex-wrap p-2">
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
            <h5 class="text-secondary">BDInput Row Text</h5>
            <DBInput :instance="instance" :property-id="property.id">
                <template #default="{set, value}">
                    <RowTextInput :model-value="value" @update:model-value="set" :width="200"/>
                </template>
            </DBInput>
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

        <!-- <div class="item border rounded">
            <h5 class="text-secondary">Color</h5>
            <span class="text-secondary">Preview</span>
            <div class="mb-1">
                 <ColorPreview :color="color" />
            </div>
            <span class="text-secondary">Input</span>
            <div>
                <ColorInput v-model="color"/>
            </div>
        </div> -->

        <div class="item border rounded">
            <h5 class="text-secondary">CellColorInput</h5>
            <div>
                <CellColorInput v-model="color" :rounded="true" />
            </div>
        </div>

        <div class="item border rounded">
            <h5 class="text-secondary">RowDateInput</h5>
            <div>
                <RowDateInput v-model="date" />
            </div>
        </div>

        <div class="item border rounded">
            <h5 class="text-secondary">Checkbox</h5>
            <span class="text-secondary">Preview</span>
            <div class="mb-1">
                 {{Boolean(checkbox)}}
            </div>
            <span class="text-secondary">Input</span>
            <div>
                <CheckboxInput v-model="checkbox" label="Checkbox"/>
            </div>
        </div>

        <div class="item border rounded">
            <h5 class="text-secondary">Tags</h5>
            <div>
                <TagInputDropdown :property="data.propertyList.find(p => p.type == PropertyType.multi_tags)" v-model="tags" :can-create="true" :no-wrap="true"/>
            </div>
        </div>

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