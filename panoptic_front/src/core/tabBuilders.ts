import { reactive } from "vue";
import { CollectionConfig, TAB_MODEL_VERSION, TabState, ViewState, ViewType } from "@/data/models";
import { createClusterOptions, createGraphOptions, createMapOptions, createRecoOptions } from "@/data/lib/builders";
import { createFilterState } from "@/core/FilterManager";
import { createSortState } from "@/core/SortManager";
import { createGroupState } from "@/core/GroupManager";
import { createCollectionState } from "@/core/CollectionManager";
import { t } from "@/locales/i18n";

export function createCollectionConfig(): CollectionConfig {
    return reactive({
        id: crypto.randomUUID(),
        collectionState: createCollectionState(),
        filterState: createFilterState(),
        sortState: createSortState(),
        groupState: createGroupState(),
    })
}

export function createViewState(type: ViewType, collectionId: string): ViewState {
    return reactive({
        type,
        imageSize: 100,
        mapOptions: createMapOptions(),
        recoOptions: createRecoOptions(),
        clusterOptions: createClusterOptions(),
        graphOptions: createGraphOptions(),
        showProperties: true,
        collectionId,
    })
}

export function buildTabState(): TabState {
    // One shared collection by default; both views reference it (computed once).
    const collection = createCollectionConfig()
    return reactive({
        version: TAB_MODEL_VERSION,
        id: '',
        name: t('main.menu.new_tab'),
        collections: [collection],
        views: [createViewState('tree', collection.id), createViewState('grid', collection.id)],
        splitView: false,
        splitRatio: 0.5,
        visibleProperties: {},
        visibleFolders: {},
        selectedFolders: {},
        propertyOptions: {},
    }) as TabState
}
