<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import * as boostrap from "bootstrap"
import { useI18n } from 'vue-i18n'

const { t } = useI18n({ useScope: 'global' })
const tooltip = ref()

const props = defineProps({
    pos: {
        type: String,
        default: "top"
    },
    message: String,
    icon: {
        type: Boolean,
        default: true
    },
    click: {
        type: Boolean,
        default: true
    }
})

const cssClass = props.click ? "cursor":""

const realMessage = computed(() => {
    if(['main', 'modals'].indexOf(props.message.split('.')[0]) > -1){
        return t(props.message)
    }
    else{
        return props.message
    }
})

onMounted(() => {
    let s = new boostrap.Tooltip(tooltip.value)
})

</script>

<template>
    <template v-if="props.icon">
        <slot/>
        <span :class="cssClass" data-bs-toggle="tooltip" :data-bs-placement="props.pos" :title="realMessage" ref="tooltip">
            <i class="bi bi-question-circle small-icon"></i>
        </span>
    </template>
    <template v-else>
        <span :class="cssClass" data-boundary="window" data-bs-toggle="tooltip" :data-bs-placement="props.pos" :title="realMessage" ref="tooltip">
            <slot /> 
        </span>
    </template>
    
</template>

<style scoped="true">
.small-icon{
    font-size: 9px;
    margin-left: 5px;
    margin-right:5px;
}
.cursor{
    cursor:pointer;
}
</style>