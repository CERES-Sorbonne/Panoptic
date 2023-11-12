<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue';
import * as bootstrap from 'bootstrap'
import { Popper } from "vue-use-popperjs";

const props = defineProps({
    offset: { default: '0,0', type: String },
    noShadow: Boolean
})
const emits = defineEmits(['show', 'hide'])
defineExpose({ hide, show, focus })

const popperElem = ref(null)
const popupElem = ref(null)
let dropdown: bootstrap.Dropdown

const visible = ref(false)
const forceVisible = ref(false)

async function hide() {
    console.log('manual hide', visible.value)
    forceVisible.value = true
    await nextTick()
    forceVisible.value = false
}

function show() {
    visible.value = true
}

function focus() {
    popupElem.value.focus()
}

async function onShow() {
    visible.value = true
    emits('show')
    await nextTick()
    focus()
}

function onHide() {
    console.log('onHide')
    visible.value = false
    emits('hide')
}

async function onEsc() {
    if(!visible.value) {
        return
    }
    forceVisible.value = true
    await nextTick()
    forceVisible.value = false
    console.log('esc')
}

onMounted(() => {
    // buttonElem.value.addEventListener('show.bs.dropdown', () => onShow())
    // buttonElem.value.addEventListener('hide.bs.dropdown', () => onHide())
    // dropdown = bootstrap.Dropdown.getOrCreateInstance(buttonElem.value)
})

</script>

<template>
    <div>
        <Popper trigger="click-to-toggle" :force-show="forceVisible" :teleport-props="{to: '#popper-holder'}" @show="onShow" @hide="onHide" ref="popperElem">
            <template #reference>
                <div class="m-0 p-0">
                    <slot name="button"></slot>
                </div>
            </template>

            <div class="popup bg-white m-0 p-0 rounded" :class="props.noShadow ? '' : 'shadow2'" style="z-index: 999;" tabindex="0" @keydown.escape="onEsc" @click.stop ref="popupElem">
                <slot name="popup" v-if="visible"></slot>
            </div>
        </Popper>
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
    box-shadow: 0px 0px 2px 2px rgba(0,0,0,0.35);
    -webkit-box-shadow: 0px 0px 3px 2px rgba(0, 0, 0, 0.185);
    -moz-box-shadow: 0px 0px 2px 2px rgba(0,0,0,0.35);
}
</style>