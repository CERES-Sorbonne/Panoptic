<script setup lang="ts">
import { nextTick, onUnmounted, ref } from 'vue';
import { Dropdown } from 'floating-vue'
import 'floating-vue/dist/style.css'
import { useProjectStore } from '@/data/projectStore';

const props = withDefaults(defineProps<{
    offset?: number
    noShadow?: boolean
    autoFocus?: boolean
    teleport?: boolean
    placement?: string
    skidding?: number
}>(), {
    placement: 'bottom',
    autoFocus: true,
    offset: 0,
    skidding: 0
})
const emits = defineEmits(['show', 'hide', 'esc', 'enter'])
defineExpose({ hide, show, focus })

const project = useProjectStore()
const popperElem = ref(null)
const popupElem = ref(null)
const buttonElem = ref(null)
const globalElem = ref(null)

const boudaryElem = ref(document.getElementsByTagName('body')[0])

const visible = ref(false)

async function hide() {
    popperElem.value.hide()
}

function show() {
    popperElem.value.show()
}

async function focus() {
    if (popupElem.value) popupElem.value.focus()
}

async function onShow() {
    visible.value = true
    if (props.autoFocus) {
        await nextTick()
        focus()
    }
    // await sleep(100)
    emits('show')
    document.addEventListener('click', clickHandler, true)
}

function onHide() {
    if (project.status.loaded && visible.value) {
        visible.value = false
        emits('hide')
    }
    document.removeEventListener('click', clickHandler, true)
}

function clickHandler(e: Event) {
    if (popupElem.value.contains(e.target) || buttonElem.value.contains(e.target)) {
    }
    else {
        hide()
    }

}

function onEscape() {
    emits('esc')
}

function onEnter(hide) {
    emits('enter', hide)
}

onUnmounted(() => {
    document.removeEventListener('click', clickHandler, true)
})

</script>

<template>
    <div class="p-0 m-0" ref="globalElem">
        <!-- <Popper trigger="click-to-toggle" :force-show="forceVisible" @show="onShow" @hide="onHide" ref="popperElem"> -->
        <Dropdown @apply-show="onShow" @hide="onHide" ref="popperElem" :distance="props.offset" :skidding="props.skidding" no-auto-focus
            :boundary="boudaryElem" :auto-hide="false" :prevent-overflow="true" :placement="props.placement"
            :container="props.teleport ? '#popup' : globalElem">
            <!-- <template #reference> -->
            <div class="m-0 p-0" ref="buttonElem">
                <slot name="button"></slot>
            </div>
            <!-- </template> -->

            <template #popper="{ hide }">
                <!-- <div class="p-1"> -->
                <div v-if="visible" class="popup bg-white m-0 p-0 rounded" :class="props.noShadow ? '' : 'dropdown-input'"
                    @keydown.escape.stop="onEscape(); hide()" @keydown.enter.stop="onEnter(hide)" style="z-index: 999;" tabindex="0" ref="popupElem">
                    <slot name="popup" :hide="hide" :focus="focus"></slot>
                </div>
                <!-- </div> -->
            </template>
        </Dropdown>
    </div>
</template>

<style scoped>
.popup {
    min-width: 0px;
    font-size: 14px;
    border: none;

    /* box-shadow: 2px 2px 4px 0px rgba(195,202,217,1);
-webkit-box-shadow: 2px 2px 4px 0px rgba(195,202,217,1);
-moz-box-shadow: 2px 2px 4px 0px rgba(195,202,217,1); */
}

.popup:focus {
    outline-width: 0;
}

.shadow2 {
    border: 2px solid var(--border-color);
    box-shadow: 0px 0px 2px 2px rgba(0, 0, 0, 0.35) !important;
    -webkit-box-shadow: 0px 0px 3px 2px rgba(0, 0, 0, 0.185) !important;
    -moz-box-shadow: 0px 0px 2px 2px rgba(0, 0, 0, 0.35) !important;
}
</style>