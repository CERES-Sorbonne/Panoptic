<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n'
import { Tooltip } from 'floating-vue'

const { t } = useI18n({ useScope: 'global' })

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

const realMessage = computed(() => {
    if (!props.message) return
    let res = ''
    if (['main', 'modals', 'dropdown', 'btn'].indexOf(props.message.split('.')[0]) > -1) {
        res = t(props.message)
    } else if (props.message.startsWith('.')) {
        res = t(props.message.slice(1))
    }
    else {
        res = props.message
    }
    const resList = res.split('\n')
    return resList
})
</script>

<template>
    <Tooltip style="display: inline;" :teleport="true" :placement="props.pos" :disabled="!props.message"
        class="m-0 p-0">
        <div class="text-nowrap d-flex m-0 p-0">
            <div v-if="props.icon && props.iconPos === 'left'" style="cursor: pointer;" class="flex-center">
                <div class="bi bi-question-circle small-icon"></div>
            </div>
            <slot></slot>
            <span v-if="props.icon && props.iconPos === 'right'" style="cursor: pointer;"> <i
                    class="bi bi-question-circle small-icon"></i></span>
        </div>
        <template #popper>
            <div style="max-width: 300px; word-break:normal; word-wrap: break-word;">
                <span v-for="line in realMessage">{{ line }}<br /></span>
            </div>
        </template>
    </Tooltip>
</template>

<style scoped="true">
.small-icon {
    font-size: 9px;
    margin-left: 5px;
    margin-right: 5px;
}
</style>