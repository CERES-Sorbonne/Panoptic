/**
 * One slot of VirtualScroller's pool. Its own component so that handing a slot another line
 * re-renders that slot alone: the scroller's own render only runs when the pool grows.
 *
 * The slot calls the scroller's default slot itself, so whatever that slot reads (the owner's
 * props, stores) is tracked by this slot's render. Its element's position is written by the
 * scroller (VirtualView.place), never through Vue: the vnode carries no style.
 */
import { InjectionKey, defineComponent, h, inject, onBeforeUnmount, onMounted, PropType, ref, VNode } from 'vue'
import type { LineRef } from './scrollLayout'
import type { Slot } from './virtualView'

export interface SlotContext {
    render(line: LineRef, slot: Slot): VNode[] | undefined
    bind(slot: Slot, el: HTMLElement | null): void
}

export const slotContextKey: InjectionKey<SlotContext> = Symbol('vsSlotContext')

export default defineComponent({
    name: 'VsSlot',
    props: {
        state: { type: Object as PropType<Slot>, required: true },
    },
    setup(props) {
        const ctx = inject(slotContextKey)!
        const el = ref<HTMLElement | null>(null)
        onMounted(() => ctx.bind(props.state, el.value))
        onBeforeUnmount(() => ctx.bind(props.state, null))
        return () => {
            const slot = props.state
            const line = slot.line.value
            return h('div', { ref: el, class: 'vs-slot', 'data-vs-type': slot.type }, (line && ctx.render(line, slot)) || [])
        }
    },
})
