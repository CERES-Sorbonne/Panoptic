<script setup lang="ts">
import { defineProps, defineEmits } from 'vue'

const props = defineProps<{
    page?: string
    options: string[]
}>()
const emits = defineEmits(['update:page'])

function changePage(page: string) {
    emits('update:page', page)
}

</script>

<template>
    <div class="d-flex h-100">
        <div class="option-list" style="min-width: 150px;">
            <div v-for="option in props.options" class="border-bottom" :class="option == props.page ? 'active' : ''">
                <div class="bb p-1 text-capitalize" style="border-radius: 0px;" @click="changePage(option)">{{ option }}
                </div>
            </div>
        </div>
        <div class="flex-grow-1 h-100">
            <div v-if="props.page != ''" class="d-flex upper mb-2">
                <div class="bb" @click="changePage('')"><i class="bi bi-arrow-left" /></div>
                <div class="text-capitalize text-secondary">{{ props.page }}</div>
                <!-- <div class="me-5"></div> -->
                <slot name="header" :page="props.page"></slot>
            </div>
            <slot :page="props.page"></slot>
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