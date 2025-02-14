<script setup lang="ts">
import SelectionStamp from '@/components/selection/SelectionStamp.vue';
import { GroupManager, SelectedImages } from '@/core/GroupManager';
import Similarity from './Similarity.vue';
import wTT from '@/components/tooltips/withToolTip.vue'
import Instances from './Instances.vue';
import { Instance } from '@/data/models';
import { Ref } from 'vue';

const props = defineProps<{
    image: Instance
    width: number
    height: number
    mode: number
    groupManager: GroupManager
    visibleProperties: { [id: number]: boolean }
    preview: SelectedImages
}>()

const emits = defineEmits(['update:mode'])

function setMode(value) {
    emits('update:mode', value)
}
</script>

<template>
    <div class="view-selection">
        <div class="d-flex">
            <div class="d-flex overflow-hidden">
                <wTT message="modals.image.similar_images_tooltip">
                    <div class="view-mode ps-2 pe-2 btn-icon" :class="(props.mode == 0 ? 'selected' : '')"
                        @click="setMode(0)">{{
                        $t('modals.image.similar_images') }}
                    </div>
                </wTT>
                <wTT message="modals.image.unique_properties_tooltip" v-if="true">
                    <div class="view-mode ps-2 pe-2 btn-icon" :class="(props.mode == 1 ? 'selected' : '')"
                        @click="setMode(1)">
                        {{ $t('modals.image.unique_properties') }}</div>
                </wTT>
            </div>
            <div class="flex-grow-1"></div>
            <div class="selection-stamp" style="line-height: 18px; margin: 3px 5px 0 0"
                v-if="Object.keys(groupManager.selectedImages.value).length > 0">
                <SelectionStamp :selected-images-ids="Object.keys(groupManager.selectedImages.value).map(Number)"
                    @remove:selected="groupManager.clearSelection()" @stamped="groupManager.clearSelection()"/>
            </div>

        </div>
    </div>
    <div class="p-1" v-if="props.mode == 0">
        <Similarity :image="image" :height="props.height - 40" :width="props.width - 10" :similar-group="groupManager"
            :visible-properties="props.visibleProperties" :preview="props.preview"/>
    </div>
    <div v-else class="p-2">
        <Instances :image="image" :height="props.height - 40" :width="props.width - 10" :group-manager="groupManager" />
    </div>
</template>

<style scoped>
.view-selection {

    background-color: white;
    /* border-bottom: 1px solid var(--border-color); */
    line-height: 30px;
}

.selected {
    background-color: white !important;
    border-bottom: none !important;
    height: 31px;
}

.view-mode {
    border-right: 1px solid var(--border-color);
    border-bottom: 1px solid var(--border-color);
    /* border-top: 1px solid var(--border-color); */
    background-color: var(--tab-grey)
}
</style>