<script setup lang="ts">
import { PropertyType, PropertyNames, PropertyMode } from '@/data/models';
import PropertyIcon from '../properties/PropertyIcon.vue';
import { onMounted, reactive, ref } from 'vue';

const props = defineProps({
    modelValue: String as () => PropertyMode
})
const emits = defineEmits(['update:modelValue'])

const modes = Object.values(PropertyMode) as PropertyMode[]

onMounted(() => {
    if(!props.modelValue) {
        emits('update:modelValue', modes[0])
    }
})

</script>

<template>
    <div class="dropdown">
        <button class="input-lg text-nowrap" type="button" data-bs-toggle="dropdown" aria-expanded="false">
            <span v-if="props.modelValue == null">Mode..</span>
            <span v-if="props.modelValue == PropertyMode.id">
                Propriété Image
            </span>
            <span v-if="props.modelValue == PropertyMode.sha1">
                Propriété Sha1
            </span>
        </button>
        <ul class="dropdown-menu">
            <li v-for="mode in modes" @click="emits('update:modelValue', mode)">
                <a class="dropdown-item" href="#">
                    {{ mode }}
                </a>
            </li>
        </ul>
    </div>
</template>