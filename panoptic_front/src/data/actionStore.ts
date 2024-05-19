import { defineStore } from "pinia";
import { useProjectStore } from "./projectStore";
import { ActionContext, Actions, ExecuteActionPayload, ParamDefaults, SearchResult } from "./models";
import { computed, reactive, ref, watch } from "vue";
import { apiCallActions, apiGetUIData, apiSetUIData } from "./api";
import { objValues } from "./builder";

const hooks = ['similar', 'group', 'execute', 'import', 'export']

export const useActionStore = defineStore('actionStore', () => {
    const project = useProjectStore()

    const index = ref({} as Actions)
    const defaultActions = reactive({
        similar: undefined,
        group: undefined,
        execute: undefined,
        import: undefined,
        export: undefined
    })

    const hasSimilaryFunction = computed(() => defaultActions.similar != undefined)

    function load() {
        if(!project.status.loaded) return
        index.value = project.actions
        const defaults = apiGetUIData('param_defaults')

        for(let action of objValues(index.value)) {
            for(let param of action.params) {
                if(defaults[param.id] !== undefined) {
                    param.defaultValue = defaults[param.id]
                }
            }
        }

        for(let key in defaultActions) {
            if(defaultActions[key] && index.value[defaultActions[key]] == undefined) {
                defaultActions[key] == undefined
            }
            if(defaultActions[key] == undefined) {
                const valid = objValues(index.value).find(a => a.hooks.includes(key))
                if(valid) {
                    defaultActions[key] = valid.id
                }
            }
        }
    }

    async function getSimilarImages(ctx: ActionContext) {
        const res = await apiCallActions({function: defaultActions.similar, context: ctx})
        return res
    }

    function clear() {
        index.value = {}
        Object.keys(defaultActions).forEach(k => defaultActions[k] = undefined)
    }

    async function updateDefaultParams() {
        const defaults = {}
        for(let action of objValues(index.value)) {
            for(let param of action.params) {
                defaults[param.id] = param.defaultValue
            }
        }
        await apiSetUIData('param_defaults', defaults)
    }

    async function updateDefaultActions(defaults: any) {
        Object.assign(defaultActions, defaults)
        await apiSetUIData('default_actions', defaultActions)
    }

    load()
    watch(() => project.status.loaded, (loaded) => {
        if (!loaded) clear()
    })
    watch(() => project.actions, load)

    return {
        index, defaultActions,
        updateParamDefaults: updateDefaultParams, updateDefaultActions,
        hasSimilaryFunction, 
        getSimilarImages,
        clear
    }
})