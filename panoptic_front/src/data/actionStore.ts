import { defineStore } from "pinia";
import { useProjectStore } from "./projectStore";
import { ActionContext, ActionFunctions, ExecuteActionPayload, VectorType } from "./models";
import { computed, reactive, ref, watch } from "vue";
import { apiGetUIData, apiSetUIData } from "./api";
import { objValues } from "./builder";
import { useDataStore } from "./dataStore";
import { sourceFromFunction } from "@/utils/utils";

const hooks = ['similar', 'group', 'execute', 'import', 'export', 'vector_type', 'vector']

export const useActionStore = defineStore('actionStore', () => {
    const project = useProjectStore()

    const index = ref({} as ActionFunctions)
    const defaultActions = reactive({
        similar: undefined,
        group: undefined,
        execute: undefined,
        import: undefined,
        export: undefined,
        vector_type: undefined,
        vector: undefined
    })
    const update = ref(0)

    const hasSimilaryFunction = computed(() => defaultActions.similar != undefined)

    async function load() {
        if (!project.status.loaded) return
        if (!Object.keys(project.actions).length) return
        const defaults = await apiGetUIData('param_defaults')

        let actionIndex = project.actions
        if (defaults) {
            for (let actionKey in actionIndex) {
                const action = actionIndex[actionKey]
                for (let param of action.params) {
                    if (defaults[param.id] !== undefined) {
                        param.defaultValue = defaults[param.id]
                    }
                }
            }
        }

        index.value = actionIndex

        for (let key in defaultActions) {
            if (defaultActions[key] && index.value[defaultActions[key]] == undefined) {
                defaultActions[key] == undefined
            }
            if (defaultActions[key] == undefined) {
                const valid = objValues(index.value).find(a => a.hooks.includes(key))
                if (valid) {
                    defaultActions[key] = valid.id
                }
            }
        }

        await getDefaultActions()
        await getDefaultParams()

        update.value += 1
    }

    async function getSimilarImages(ctx: ActionContext) {
        const res = await project.call({ function: defaultActions.similar, context: ctx })
        return res
    }

    function clear() {
        index.value = {}
        Object.keys(defaultActions).forEach(k => defaultActions[k] = undefined)
    }

    async function updateDefaultParams() {
        const defaults = {}
        for (let action of objValues(index.value)) {
            for (let param of action.params) {
                defaults[action.id + '.' + param.name] = param.defaultValue
            }
        }
        await apiSetUIData('param_defaults', defaults)
    }

    async function getDefaultParams() {
        const res = await apiGetUIData('param_defaults')
        if (!res) return
        for (let action of objValues(index.value)) {
            for (let param of action.params) {
                const key = action.id + '.' + param.name
                if (key in res) {
                    param.defaultValue = res[key]
                }
            }
        }
    }

    async function updateDefaultActions(defaults: any) {
        Object.assign(defaultActions, defaults)
        await apiSetUIData('default_actions', defaultActions)
    }

    async function getDefaultActions() {
        const res = await apiGetUIData('default_actions')
        if (!res) {
            return
        }
        for (let key of Object.keys(res)) {
            if (!index.value[res[key]]) {
                delete res[key]
            }
        }
        Object.assign(defaultActions, res)
    }

    function getContext(funcName: string) {
        const data = useDataStore()
        const ctx: ActionContext = { uiInputs: {} }
        const act = index.value[funcName]
        for (let param of act.params) {
            // ctx.uiInputs[param.name] = param.defaultValue
            // Set default Value
            let baseValue = param.defaultValue

            // Verify value is valid
            if (baseValue != undefined) {
                if (param.type == 'vector_type') {
                    const type_id = baseValue.id
                    if (data.vectorTypes.findIndex(v => v.id == type_id) < 0) {
                        baseValue = undefined
                    }
                }
                if (param.type == 'own_vector_type') {
                    const type_id = baseValue.id
                    const source = sourceFromFunction(funcName)
                    const index = data.vectorTypes.findIndex(v => v.id == type_id)
                    if (index < 0 || data.vectorTypes[index].source != source) {
                        baseValue = undefined
                    }
                }
                if (param.type == 'property') {
                    if (!data.properties[baseValue]) {
                        baseValue = undefined
                    }
                }
            }

            // Find any value to set
            if (baseValue == undefined) {
                if (param.type == 'vector_type') {
                    if (data.vectorTypes.length) {
                        baseValue = data.vectorTypes[0]
                    }
                }
                if (param.type == 'own_vector_type') {
                    const source = sourceFromFunction(funcName)
                    let first = data.vectorTypes.find(v => v.source = source)
                    if (first) {
                        baseValue = first
                    }
                }
                if (param.type == 'property') {
                    if (data.propertyList.length) {
                        baseValue = data.propertyList[0].id
                    }
                }
            }

            ctx.uiInputs[param.name] = baseValue

        }
        return ctx
    }

    async function callComputeVector(vecType: VectorType) {
        let functions = objValues(index.value).filter(f => sourceFromFunction(f.id) == vecType.source && f.hooks.includes('vector'))
        if (functions.length) {
            let fnc = functions[0]
            let ctx = getContext(fnc.id)
            let vec_param = fnc.params.find(p => p.type == 'own_vector_type')

            if (vec_param) {
                ctx.uiInputs[vec_param.name] = vecType
                console.log(ctx)
            }
            const req2: ExecuteActionPayload = { function: fnc.id, context: ctx }
            return await project.call(req2)
        }
    }

    load()
    watch(() => project.status.loaded, (loaded) => {
        if (!loaded) clear()
    })
    watch(() => project.actions, load)

    return {
        index, defaultActions,
        updateDefaultParams, updateDefaultActions,
        hasSimilaryFunction,
        getSimilarImages, getContext,
        clear, update, load, callComputeVector
    }
})