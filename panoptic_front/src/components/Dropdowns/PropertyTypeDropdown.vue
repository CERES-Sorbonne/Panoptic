<script setup lang="ts">
import { PropertyType, PropertyNames } from '@/data/models';
import PropertyIcon from '../properties/PropertyIcon.vue';
import { computed, reactive, ref } from 'vue';

const props = defineProps({
    modelValue: String as () => PropertyType
})
const emits = defineEmits(['update:modelValue'])

const types = Object.keys(PropertyType).filter(k => k[0] != '_').map((k:any) => (PropertyType as any)[k] as PropertyType) as PropertyType[]
const filtered = computed(() => types.filter(t => t != PropertyType.image_link && t != PropertyType.path))
</script>

<template>
    <div class="dropdown">
        <button class="input-lg text-nowrap" type="button" data-bs-toggle="dropdown" aria-expanded="false">
            <span v-if="props.modelValue == null">Type de propriété..</span>
            <span v-else>
                <PropertyIcon :type="props.modelValue"/>
                {{ PropertyNames[props.modelValue] }}
            </span>
        </button>
        <ul class="dropdown-menu">
            <li v-for="type_ in filtered" @click="emits('update:modelValue', type_)">
                <a class="dropdown-item" href="#">
                    <PropertyIcon :type="type_"/>
                    {{ PropertyNames[type_] }}
                </a>
            </li>
        </ul>
    </div>
</template>