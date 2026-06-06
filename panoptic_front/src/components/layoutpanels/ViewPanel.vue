<script setup lang="ts">
// A single view island root node — wraps the image visualisation in a growing
// island card. Used once per pane in the center view split.
import IslandPanel from '@/layouts/IslandPanel.vue'
import ImageView from '@/components/mainview/ImageView.vue'
</script>

<template>
    <IslandPanel grow>
        <ImageView />
    </IslandPanel>
</template>
