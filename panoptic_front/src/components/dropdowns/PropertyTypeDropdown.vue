<script setup lang="ts">
import { PropertyType } from '@/data/models';
import PropertyIcon from '../properties/PropertyIcon.vue';
import wTT from '../tooltips/withToolTip.vue'
import { computed } from 'vue';
import { goNext } from '@/utils/utils';
import Dropdown from './Dropdown.vue';

const props = defineProps({
    modelValue: String as () => PropertyType
})
const emits = defineEmits(['update:modelValue'])

const types = Object.keys(PropertyType).filter(k => k[0] != '_').map((k: any) => (PropertyType as any)[k] as PropertyType) as PropertyType[]
const filtered = computed(() => types.filter(t => t != PropertyType.image_link && t != PropertyType.path))
</script>

<template>
    <Dropdown :teleport="true">
        <template #button>
            <div class="bbb">
                <span v-if="props.modelValue == null">{{ $t('modals.properties.type') }}</span>
                <span v-else>
                    <PropertyIcon :type="props.modelValue" />
                    {{ $t('modals.properties.' + props.modelValue) }}
                </span>
            </div>
        </template>
        <template #popup="{hide}">
            <div class="p-2" style="font-size: 16px;">
                <div class="bb" v-for="type_ in filtered" @click="emits('update:modelValue', type_); hide()">
                    <wTT :message="'modals.properties.' + type_ + '_tooltip'">
                        <PropertyIcon class="me-1" :type="type_" />
                        {{ $t('modals.properties.' + type_) }}
                    </wTT>
                </div>
            </div>
        </template>
    </Dropdown>
</template>