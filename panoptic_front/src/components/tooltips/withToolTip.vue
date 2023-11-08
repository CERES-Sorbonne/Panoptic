<script setup lang="ts">
import { computed, onMounted, ref, nextTick, useSlots  } from 'vue';
import * as boostrap from "bootstrap"
import { useI18n } from 'vue-i18n'

const { t } = useI18n({ useScope: 'global' })
const tooltipRef = ref()

let tooltip = null

const props = defineProps({
    pos: {
        type: String,
        default: "top"
    },
    message: String,
    icon: {
        type: Boolean,
        default: false
    },
    iconPos: {
        type: String,
        default: "right"
    },
    click: {
        type: Boolean,
        default: true
    }
})

const cssClass = props.click ? "cursor wtt":"wtt"

const realMessage = computed(() => {
    if(['main', 'modals'].indexOf(props.message.split('.')[0]) > -1){
        return t(props.message)
    }
    else{
        return props.message
    }
})

onMounted(async () => {
    tooltip = new boostrap.Tooltip(tooltipRef.value, {trigger: 'hover'})
})

function hide() {
    // needed to avoid some bug where tooltip wouldnt disapear after a button click 
    tooltip.hide()
}
</script>

<template>
    <template v-if="props.icon">
        <slot v-if="props.iconPos==='right'"/>
        <span :class="cssClass" data-bs-toggle="tooltip" data-bs-trigger="hover" :data-bs-placement="props.pos" :title="realMessage" ref="tooltipRef" @click="hide()">
            <i class="bi bi-question-circle small-icon"></i>
        </span>
        <slot v-if="props.iconPos==='left'" />
    </template>
    <template v-else>
        <span :class="cssClass" data-bs-toggle="tooltip" data-bs-trigger="hover" :data-bs-placement="props.pos" :title="realMessage" ref="tooltipRef" @click="hide()">
            <slot/> 
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

.tooltip{
    font-size:2px !important;
}

.wtt{
    /* display: contents; */
}
</style>