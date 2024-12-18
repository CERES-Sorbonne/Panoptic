<script setup lang="ts">
import { PropertyMode } from '@/data/models';
import { onMounted } from 'vue';
import Dropdown from './Dropdown.vue';

const props = defineProps({
    modelValue: String as () => PropertyMode
})
const emits = defineEmits(['update:modelValue'])

const modes = Object.values(PropertyMode) as PropertyMode[]

onMounted(() => {
    if (!props.modelValue) {
        emits('update:modelValue', modes[0])
    }
})

</script>

<template>
    <Dropdown :teleport="true">
        <template #button>
            <div class="bbb">
                <span v-if="props.modelValue == null">Mode..</span>
                <span v-if="props.modelValue == PropertyMode.id">
                    {{$t('modals.properties.instance')}}
                </span>
                <span v-if="props.modelValue == PropertyMode.sha1">
                    {{$t('modals.properties.image')}}
                </span>
            </div>
        </template>
        <template #popup="{hide}">
            <div class="p-2 text-nowrap">
                <div class="bb" @click="emits('update:modelValue', PropertyMode.id); hide()"> {{$t('modals.properties.instance')}} </div>
                <div class="bb" @click="emits('update:modelValue', PropertyMode.sha1); hide()"> {{$t('modals.properties.image')}} </div>
            </div>
        </template>
    </Dropdown>
</template>