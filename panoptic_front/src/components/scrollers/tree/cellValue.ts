import { InjectionKey } from 'vue'

// The property and raw value of the row a tree cell frame is drawing, for the frame's own
// actions (filter by this value). Not provided outside the tree/cluster scrollers.
export const cellValueKey: InjectionKey<() => { propertyId: number, value: any }> = Symbol('cellValue')
