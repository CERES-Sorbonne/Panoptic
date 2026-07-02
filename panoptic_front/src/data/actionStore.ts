import { defineStore } from "pinia";
import { useProjectStore } from "./projectStore";
import { ActionContext, ActionResult, ActionFunctions, ExecuteActionPayload, FunctionDescription, ParamDescription, VectorType } from "./models";
import { computed, reactive, ref, watch } from "vue";
import { objValues } from "./builder";
import { useDataStore } from "./dataStore";
import { useMediaStore } from "./mediaStore";
import { convertClusterGroupResult, fileToBase64, sourceFromFunction } from "@/utils/utils";
import { ClusterParam, Group } from "@/core/GroupManager";
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
        const media = useMediaStore()
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
                    if (media.vectorTypes.findIndex(v => v.id == type_id) < 0) {
                        baseValue = undefined
                    }
                }
                if (param.type == 'own_vector_type') {
                    const type_id = baseValue.id
                    const source = sourceFromFunction(funcName)
                    const index = media.vectorTypes.findIndex(v => v.id == type_id)
                    if (index < 0 || media.vectorTypes[index].source != source) {
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
                    if (media.vectorTypes.length) {
                        baseValue = media.vectorTypes[0]
                    }
                }
                if (param.type == 'own_vector_type') {
                    const source = sourceFromFunction(funcName)
                    let first = media.vectorTypes.find(v => v.source == source)
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

    async function executeAction(funcId: string, hook: string, ctx: ActionContext, inputs: ParamDescription[]): Promise<{ result: ActionResult; groups?: Group[] }> {
        const data = useDataStore()
        const localInputs = JSON.parse(JSON.stringify(inputs))
        const uiInputs: Record<string, any> = {}
        const clusterInputs: ClusterParam[] = []

        for (let input of localInputs) {
            if (input.type == 'property' && !input.defaultValue && data.propertyList.length) {
                input.defaultValue = data.propertyList[0].id
            }
            clusterInputs.push({
                name: input.name,
                label: input.label,
                value: input.type == 'input_file' && input.defaultValue ? input.defaultValue.name : input.defaultValue
            })
            if (input.type == 'input_file' && input.defaultValue) {
                input.defaultValue = await fileToBase64(input.defaultValue)
            }
            uiInputs[input.name] = input.defaultValue
        }

        ctx.uiInputs = uiInputs
        const req: ExecuteActionPayload = { function: funcId, context: ctx }
        const res = await project.call(req)

        let groups: Group[] | undefined
        if (res.groups) {
            groups = convertClusterGroupResult(res.groups, ctx, { function: funcId, inputs: clusterInputs })
        }

        for (let i in localInputs) {
            index.value[funcId].params[i].defaultValue = localInputs[i].defaultValue
        }
        await updateDefaultParams(funcId)

        const update: Record<string, string> = {}
        update[hook] = funcId
        await updateDefaultActions(update)

        return { result: res, groups }
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
        clear, init, reload, executeAction, callComputeVector,
        textSearchFunctions
    }
})