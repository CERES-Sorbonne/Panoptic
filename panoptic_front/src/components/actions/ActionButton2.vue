<script setup lang="ts">
import { ref, onMounted, watch, computed, inject } from 'vue';
import Dropdown, { dropdownRegistryKey } from '../dropdowns/Dropdown.vue';
import { ActionContext, Instance, ParamDescription } from '@/data/models';
import { useActionStore } from '@/data/stores/actionStore';
import wTT from '@/components/tooltips/withToolTip.vue'
import Autofocus from '../utils/Autofocus.vue';
import ActionForm from './ActionForm.vue';
import ViewModal from '../utils/ViewModal.vue';
import { viewModalScopeKey } from '@/data/composables/viewModal';

const actions = useActionStore()

const props = defineProps<{
    action: string
    images?: Instance[] | (() => Instance[])
    propertyIds?: number[],
    autoCall?: boolean,
    noBorder?: boolean,
    // Hand-off mode: instead of awaiting the action itself, the button emits `submit` with the
    // chosen function + params and is done. Whoever owns the operation (the ClusterManager) runs
    // it, so the result no longer depends on this button still being mounted. `busy` is then the
    // pending state read back from that owner.
    defer?: boolean,
    busy?: boolean,
    // Replaces the default tooltip, e.g. to say why the last run failed.
    message?: string
}>()
const emits = defineEmits(['instances', 'groups', 'call', 'submit', 'show', 'hide'])

// Inside a view (or the top bar) the form opens as a modal centered over the view area;
// elsewhere (e.g. the image modal) it stays a dropdown.
const modalScope = inject(viewModalScopeKey, null)
// When this button sits in another dropdown's popup (e.g. a group line menu), that
// dropdown is closed once the modal is done.
const parentDropdown = inject(dropdownRegistryKey, null)
const modalOpen = ref(false)

const localInputs = ref<ParamDescription[]>([])
const defaultFunction = computed(() => actions.defaultActions[props.action])
const localFunction = ref<string>(null)
const loading = ref(false)
const dropdownElem = ref(null)
const formElem = ref(null)

function loadAction() {
    localFunction.value = defaultFunction.value
    loadInput()
}

function loadInput() {
    const funcId = localFunction.value
    if (!funcId) return

    if (!actions.index[funcId]) return
    const params = actions.index[funcId].params
    const defaults = actions.getContext(funcId).uiInputs

    for (let param of params) {
        param.defaultValue = defaults[param.name]
    }

    localInputs.value = JSON.parse(JSON.stringify(params))
}

const pending = computed(() => props.defer ? !!props.busy : loading.value)

async function call() {
    if (pending.value) return

    if (props.defer) {
        emits('submit', { funcId: localFunction.value, inputs: localInputs.value, hook: props.action })
        return
    }

    const imgs = typeof props.images === 'function' ? props.images() : (props.images ?? [])

    loading.value = true
    try {
        const imageIds = imgs.map(i => i.id)
        const context: ActionContext = { instanceIds: imageIds, propertyIds: props.propertyIds }
        const { result, groups } = await actions.executeAction(localFunction.value, props.action, context, localInputs.value)
        if (groups) {
            emits('groups', groups)
        }
        emits('call', result)
    } catch (e) {
        console.error(e)
    }

    loading.value = false
}

function handleShow() {
    formElem.value?.reset()
    loadAction()
    emits('show')
}

function openModal() {
    if (props.autoCall) {
        call()
        return
    }
    handleShow()
    modalOpen.value = true
}

function onModalClosed() {
    emits('hide')
    parentDropdown?.hide()
}

function callFromModal() {
    call()
    modalOpen.value = false
    onModalClosed()
}

onMounted(loadAction)
watch(() => actions.index, loadAction)
watch(defaultFunction, loadAction)
watch(() => props.action, loadAction)
watch(localFunction, loadInput)
</script>

<template>
    <!-- Single root (attrs fall through); the modal is teleported, so its clicks never
         reach this element's click handler. -->
    <div v-if="modalScope !== null" class="d-flex main2" :class="{ sbb: !props.noBorder, sb: props.noBorder }"
        @click="openModal">
            <div v-if="pending" class="spinner-border spinner-border-sm text-primary me-1" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <wTT :message="props.message ?? 'dropdown.action.' + props.action" class="slot-wrap">
                <div class="slot-inner">
                    <slot></slot>
                </div>
            </wTT>
        <ViewModal v-model:show="modalOpen" :scope="modalScope" :width="440" @close="onModalClosed">
            <template #title>{{ $t('action.' + props.action) }}</template>
            <ActionForm ref="formElem" :action="props.action" :inputs="localInputs" v-model:func="localFunction"
                @call="callFromModal" @cancel="modalOpen = false; onModalClosed()" />
        </ViewModal>
    </div>
    <Dropdown v-else :teleport="true" @show="handleShow" @hide="emits('hide')" ref="dropdownElem">
        <template #button>
            <div class="d-flex main2" :class="{ sbb: !props.noBorder, sb: props.noBorder }">
                <div v-if="pending" class="spinner-border spinner-border-sm text-primary me-1" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <wTT :message="props.message ?? 'dropdown.action.' + props.action" class="slot-wrap">
                    <div class="slot-inner">
                        <slot></slot>
                    </div>
                </wTT>
            </div>
        </template>
        <template #popup="{ hide }">
            <Autofocus>
                <ActionForm ref="formElem" :action="props.action" :inputs="localInputs" v-model:func="localFunction"
                    :width="400" @call="call(); hide();" @cancel="hide()" />
            </Autofocus>
        </template>
    </Dropdown>
</template>

<style scoped>
.main2 {
    cursor: pointer;
    align-items: center;
    height: 100%;
}

.slot-wrap {
    display: flex;
    align-items: center;
    height: 100%;
}

.slot-inner {
    display: flex;
    align-items: center;
    height: 100%;
}
</style>
