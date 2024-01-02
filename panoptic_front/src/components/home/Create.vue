<script setup lang="ts">
import { computed, ref } from 'vue';

const emits = defineEmits(['cancel', 'create'])

const path = ref('')
const name = ref('')

const validForm = computed(() => path.value != '' && name.value != '')

function selectFolder() {

}


</script>

<template>
    <div class="">
        <h3 class="mb-3">{{$t('main.home.create_title')}}</h3>
        <div class="d-flex text-start input mb-2">
            <div class="info">{{ $t('main.home.label.folder') }}</div>
            <div class="flex-grow-1 value text-dim">
                <span v-if="path != ''">{{ path }}</span>
                <span v-else class="text-placeholder">{{ $t('main.home.label.path_placeholder') }}</span>
            </div>
            <div class="folder"><i class="bi bi-folder"></i></div>
        </div>

        <div class="d-flex text-start input">
            <div class="info">{{ $t('main.home.label.name') }}</div>
            <div class="flex-grow-1 value text-dim">
                <input type="text" v-model="name" placeholder="project_name" style="width: 100%;"/>
            </div>
        </div>

        <div class="d-flex mt-2">
            <div class="flex-grow-1"></div>
            <div class="btn-grey hover-grey" @click="emits('cancel')">{{ $t('main.home.label.cancel') }}</div>
            <div class="ms-2" :class="validForm ? 'btn-blue' : 'btn-grey text-dim'">{{ $t('main.home.label.create') }}</div>
        </div>
    </div>
</template>

<style scoped>
.input {
    border: 1px solid var(--border-color);
    border-radius: 5px;
    overflow: hidden;
}

.info {
    background-color: var(--grey);
    padding: 5px 10px;
}

.value {
    border-left: 1px solid var(--border-color);
    padding: 5px 10px;
}

.folder {
    padding: 5px;
    background-color: var(--grey);
    border-left: 1px solid var(--border-color);
    cursor: pointer;
}

input {
    border: none;
}
</style>