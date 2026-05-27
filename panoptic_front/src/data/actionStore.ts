import { defineStore } from "pinia";
import { useProjectStore } from "./projectStore";
import { ActionContext, ActionFunctions, ExecuteActionPayload, FunctionDescription, VectorType } from "./models";
import { computed, reactive, ref, watch } from "vue";
import { objValues } from "./builder";
import { useDataStore } from "./dataStore";
import { sourceFromFunction } from "@/utils/utils";
import { apiGetActions, apiGetAllUIData, apiSetUIDataBulk } from "./apiProjectRoutes";

export const useActionStore = defineStore('actionStore', () => {
    const project = useProjectStore()

    const loaded = ref(false)

    const index = ref({} as ActionFunctions)
    const defaultActions = reactive({
        similar: undefined,
        group: undefined,
        execute: undefined,
        import: undefined,
        export: undefined,
        vector_type: undefined,
        vector: undefined,
        map: undefined
    })

    const hasSimilaryFunction = computed(() => defaultActions.similar != undefined)
    const hasVectorFunction = computed(() => defaultActions.vector_type != undefined)

    const textSearchFunctions = computed(() => objValues(index.value).filter(f => f.hooks.includes('text_search')))

    async function init() {
        const actions = await apiGetActions()
        await loadActions(actions)

        loaded.value = true
    }

    async function loadActions(actions: ActionFunctions) {
        index.value = actions

        for (let key in defaultActions) {
            if (defaultActions[key] && index.value[defaultActions[key]] == undefined) {
                defaultActions[key] = undefined
            }
            if (defaultActions[key] == undefined) {
                const valid = objValues(index.value).find(a => a.hooks.includes(key))
                if (valid) {
                    defaultActions[key] = valid.id
                }
            }
        }

        const allUIData = await apiGetAllUIData()
        _applyDefaultActions(allUIData)
        _applyDefaultParams(allUIData)
    }

    async function getSimilarImages(ctx: ActionContext) {
        const res = await project.call({ function: defaultActions.similar, context: ctx })
        return res
    }

    function clear() {
        loaded.value = false
        index.value = {}
        Object.keys(defaultActions).forEach(k => defaultActions[k] = undefined)
    }

    async function reload() {
        loaded.value = false
        await init()
    }

    async function updateDefaultParams(funcId: string) {
        const action = index.value[funcId]
        if (!action) return
        const bulk: Record<string, any> = {}
        for (let param of action.params) {
            if (param.defaultValue != null) {
                bulk[`param.${funcId}.${param.name}`] = param.defaultValue
            }
        }
        if (Object.keys(bulk).length) {
            await apiSetUIDataBulk(bulk)
        }
    }

    function _applyDefaultParams(allUIData: Record<string, any>) {
        for (let action of objValues(index.value)) {
            for (let param of action.params) {
                const key = `param.${action.id}.${param.name}`
                if (key in allUIData) {
                    param.defaultValue = allUIData[key]
                }
            }
        }
    }

    async function updateDefaultActions(defaults: any) {
        Object.assign(defaultActions, defaults)
        const bulk: Record<string, any> = {}
        for (let key in defaults) {
            if (defaults[key] != null) {
                bulk[`default_action.${key}`] = defaults[key]
            }
        }
        if (Object.keys(bulk).length) {
            await apiSetUIDataBulk(bulk)
        }
    }

    function _applyDefaultActions(allUIData: Record<string, any>) {
        for (let key of Object.keys(allUIData)) {
            if (!key.startsWith('default_action.')) continue
            const actionKey = key.slice('default_action.'.length)
            if (!(actionKey in defaultActions)) continue
            const funcId = allUIData[key]
            if (funcId && !index.value[funcId]) continue
            defaultActions[actionKey] = funcId
        }
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
                    let first = data.vectorTypes.find(v => v.source == source)
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
                // console.log(ctx)
            }
            const req2: ExecuteActionPayload = { function: fnc.id, context: ctx }
            return await project.call(req2)
        }
    }

    return {
        index, defaultActions,
        updateDefaultParams, updateDefaultActions,
        hasSimilaryFunction, hasVectorFunction,
        getSimilarImages, getContext,
        clear, init, reload, callComputeVector,
        textSearchFunctions
    }
})