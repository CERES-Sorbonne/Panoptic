<script setup lang="ts">
import { defineProps, defineEmits } from 'vue'

const props = defineProps<{
    page?: string
    options: string[]
    langKey?: string
}>()
const emits = defineEmits(['update:page'])

function changePage(page: string) {
    emits('update:page', page)
}

</script>

<template>
    <div class="d-flex h-100">
        <div class="option-list" style="min-width: 150px;">
            <div
            v-for="option in props.options"
            :key="option"
            class="border-bottom bb p-1 text-capitalize"
            :class="{ active: option === props.page }"
            @click="changePage(option)"
            style="border-radius: 0px;"
            >
            <span v-if="props.langKey">{{ $t(props.langKey + '.' + option) }}</span>
            <span v-else>{{ option }}</span>
            </div>
        </div>
        <div class="flex-grow-1 h-100">
            <div class="d-flex flex-column h-100">
                <div v-if="props.page != ''" class="d-flex upper">
                    <div class="bb" @click="changePage('')"><i class="bi bi-arrow-left" /></div>
                    <div class="text-capitalize text-secondary">
                        <span v-if="props.langKey">{{ $t(props.langKey + '.' + props.page) }}</span>
                        <span v-else>{{ props.page }}</span>
                    </div>
                    <!-- <div class="me-5"></div> -->
                    <slot name="header" :page="props.page"></slot>
                </div>
                <div class="flex-grow-1" style="overflow-y: auto; overflow-x: hidden;">
                    <slot :page="props.page"></slot>
                </div>
            </div>

        </div>
    </div>
</template>

<style scoped>
.upper {
    border-bottom: 1px solid var(--border-color);
    padding: 3px;
}

.option-list {
    border-right: 1px solid var(--border-color);
}

.active {
    background-color: var(--light-grey);
}
</style>