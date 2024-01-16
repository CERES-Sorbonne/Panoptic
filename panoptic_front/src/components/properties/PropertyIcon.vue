<script setup lang="ts">
import { PropertyType } from '@/data/models';

const props = defineProps(['type'])
</script>

<template>
        <span>
                <i v-if="props.type == PropertyType.string" class="bi bi-text-left"></i>
                <i v-else-if="props.type == PropertyType.number" class="bi bi-123"></i>
                <i v-else-if="props.type == PropertyType.date" class="bi bi-calendar-date"></i>
                <i v-else-if="props.type == PropertyType.path" class="bi bi-code-slash"></i>
                <i v-else-if="props.type == PropertyType.image_link" class="bi bi-card-image"></i>
                <i v-else-if="props.type == PropertyType.url" class="bi bi-globe"></i>
                <i v-else-if="props.type == PropertyType.color" class="bi bi-palette"></i>
                <i v-else-if="props.type == PropertyType.checkbox" class="bi bi-check-square"></i>
                <i v-else-if="type == PropertyType.tag" class="bi bi-tag-fill"></i>
                <i v-else-if="type == PropertyType.multi_tags" class="bi bi-tags-fill"></i>
                <i v-else-if="props.type == PropertyType._folders" class="bi bi-folder"></i>
                <b v-else-if="props.type == PropertyType._id" style="padding-left: 2px;">ID</b>
                <i v-else-if="props.type == PropertyType._width" class="bi bi-arrows"></i>
                <i v-else-if="props.type == PropertyType._height" class="bi bi-arrows-vertical"></i>

                <i v-else class="bi bi-hash"></i>
        </span>
</template>