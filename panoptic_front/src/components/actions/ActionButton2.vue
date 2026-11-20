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
import { ClusterRequest, clusterErrorText } from '@/core/group/ClusterManager';
import { i18n } from '@/locales/i18n';

const actions = useActionStore()

const props = defineProps<{
    action: string
    images?: Instance[] | (() => Instance[])
    propertyIds?: number[],
    autoCall?: boolean,
    noBorder?: boolean,
    // Hand-off mode: instead of awaiting the action itself, the button hands the chosen function +
    // params to `@submit` and is done. Whoever owns the operation (the ClusterManager) runs it, so
    // the result no longer depends on this button still being mounted. `busy` is then the pending
    // state read back from that owner.
    // Declared as a prop (not an emit) so its return value reaches us: the handler may return a
    // promise of the run's outcome — resolving to undefined on success or to an error code /
    // message, or rejecting — which the view modal waits on before closing. A bare
    // `@submit="handler"` binds to it, so callers just `return manager.cluster(...)`.
    defer?: boolean,
    busy?: boolean,
    onSubmit?: (req: ClusterRequest) => unknown,
    // Replaces the default tooltip, e.g. to say why the last run failed.
    message?: string
}>()
const emits = defineEmits(['instances', 'groups', 'call', 'show', 'hide'])

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

// Runs the action; resolves to an error message when it failed, undefined otherwise (also when
// it was ignored because a run is already pending). Never rejects.
async function call(): Promise<string | undefined> {
    if (pending.value) return undefined

    if (props.defer) {
        try {
            const res = await props.onSubmit?.({ funcId: localFunction.value, inputs: localInputs.value, hook: props.action })
            return typeof res === 'string' && res ? clusterErrorText(res) : undefined
        } catch (e: any) {
            return e?.message ? String(e.message) : String(e)
        }
    }

    const imgs = typeof props.images === 'function' ? props.images() : (props.images ?? [])

    loading.value = true
    let error: string | undefined
    try {
        const imageIds = imgs.map(i => i.id)
        const context: ActionContext = { instanceIds: imageIds, propertyIds: props.propertyIds }
        const { result, groups } = await actions.executeAction(localFunction.value, props.action, context, localInputs.value)
        // apiCallActions swallows backend errors (the axios interceptor already notified them)
        // and yields no result: that is the only failure signal we get.
        if (!result) error = i18n.global.t('action_modal.no_result')
        if (groups) {
            emits('groups', groups)
        }
        emits('call', result)
    } catch (e: any) {
        console.error(e)
        error = e?.message ? String(e.message) : String(e)
    }

    loading.value = false
    return error
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

// Modal submit, mirroring the search modal (TextSearchInput): the modal stays open (form
// disabled, spinner, "Running…") until the run is over, then closes. On failure it stays open
// with the error. Esc / backdrop while pending just closes it: the run keeps going (no
// cancellation) and the trigger's spinner shows it. The sequence counter keeps a stale run from
// closing / erroring a modal reopened since.
const submitting = ref(false)
const runError = ref<string | null>(null)
let submitSeq = 0

async function callFromModal() {
    if (submitting.value || pending.value) return
    runError.value = null
    const seq = ++submitSeq
    submitting.value = true
    const error = await call()
    if (seq !== submitSeq) return
    submitting.value = false
    if (error) {
        runError.value = error
        return
    }
    if (modalOpen.value) {
        modalOpen.value = false
        onModalClosed()
    }
}

// Closing (Esc, backdrop, ×, Cancel) detaches the modal from any run still going.
function closeModal() {
    modalOpen.value = false
    onModalClosed()
}

watch(modalOpen, open => {
    if (open) return
    submitSeq++
    submitting.value = false
    runError.value = null
})

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
        <!-- Bare: ActionForm draws the header (title, close) and footer itself -->
        <ViewModal v-model:show="modalOpen" :scope="modalScope" :width="460" bare @close="onModalClosed">
            <ActionForm ref="formElem" :action="props.action" :inputs="localInputs" v-model:func="localFunction"
                :title="$t('action.' + props.action)" :busy="pending || submitting" :running="submitting"
                :error="runError" @call="callFromModal" @cancel="closeModal" />
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
                    :width="400" :busy="pending" @call="call(); hide();" @cancel="hide()" />
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
