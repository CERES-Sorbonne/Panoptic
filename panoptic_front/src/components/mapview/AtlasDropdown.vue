<script setup lang="ts">
// Atlas button in the map toolbar. The button carries a one-glance status (generating, loading,
// images missing); the popup lists the atlas coverage, sheet-load progress and a (re)generate
// action.
import { computed } from 'vue'
import Dropdown from '../dropdowns/Dropdown.vue'
import { useMediaStore } from '@/data/stores/mediaStore'
import type { AtlasLoadProgress } from '@/mixins/mapview/AtlasLayerManager'

const media = useMediaStore()

const props = defineProps<{
    // Sheet-load progress of the renderer's latest atlas load (null until a load starts).
    load: AtlasLoadProgress | null
    // Points on the current map with no atlas cell, which the map cannot draw.
    mapMissing: number
}>()

const loading = computed(() => !!props.load && props.load.loaded + props.load.failed < props.load.total)
const loadPercent = computed(() => {
    const p = props.load
    return p && p.total > 0 ? Math.round(100 * (p.loaded + p.failed) / p.total) : 0
})
const coverage = computed(() => media.atlasCoverage)
const needsAttention = computed(() =>
    (media.atlasFetched && !media.hasAtlas) || coverage.value.missing > 0 || props.mapMissing > 0 || (props.load?.failed ?? 0) > 0)

const fmt = (n: number) => n.toLocaleString()
</script>

<template>
    <Dropdown :auto-focus="false">
        <template #button>
            <div class="atlas-btn" :title="$t('map.atlas')">
                <i class="bi bi-grid-3x3-gap"></i>
                <span v-if="media.atlasTask" class="status tabular-nums">{{ media.atlasTaskPercent }}%</span>
                <span v-else-if="loading" class="status tabular-nums">{{ loadPercent }}%</span>
                <i v-else-if="needsAttention" class="bi bi-exclamation-triangle-fill warn"></i>
            </div>
        </template>
        <template #popup>
            <div class="atlas-popup">
                <div class="title">{{ $t('map.atlas') }}</div>

                <template v-if="media.atlasTask">
                    <div class="row">
                        <span class="grow">{{ $t('map.atlas_generating') }}</span>
                        <span class="tabular-nums">{{ media.atlasTaskPercent }}%</span>
                    </div>
                    <div class="bar"><div :style="{ width: media.atlasTaskPercent + '%' }"></div></div>
                </template>

                <div v-if="!media.hasAtlas" class="row muted">{{ $t('map.atlas_none_title') }}</div>
                <template v-else>
                    <div class="row">
                        <span class="grow">{{ $t('map.atlas_images') }}</span>
                        <span class="tabular-nums">{{ fmt(coverage.inAtlas) }} / {{ fmt(coverage.total) }}</span>
                    </div>
                    <div v-if="coverage.missing > 0" class="row warn">
                        <span class="grow">{{ $t('map.atlas_missing') }}</span>
                        <span class="tabular-nums">{{ fmt(coverage.missing) }}</span>
                    </div>
                    <div v-if="props.mapMissing > 0" class="row warn">
                        <span class="grow">{{ $t('map.atlas_map_missing') }}</span>
                        <span class="tabular-nums">{{ fmt(props.mapMissing) }}</span>
                    </div>
                    <template v-if="props.load">
                        <div class="row" :class="{ muted: !loading }">
                            <span class="grow">{{ loading ? $t('map.atlas_loading') : $t('map.atlas_loaded') }}</span>
                            <span class="tabular-nums">{{ props.load.loaded }} / {{ props.load.total }}</span>
                        </div>
                        <div v-if="loading" class="bar"><div :style="{ width: loadPercent + '%' }"></div></div>
                        <div v-if="props.load.failed > 0" class="row warn">
                            <span class="grow">{{ $t('map.atlas_failed') }}</span>
                            <span class="tabular-nums">{{ props.load.failed }}</span>
                        </div>
                    </template>
                </template>

                <button v-if="!media.atlasTask" class="generate" :disabled="media.atlasRequested"
                    @click="media.generateAtlas()">
                    {{ media.hasAtlas ? $t('map.atlas_regenerate') : $t('map.atlas_generate') }}
                </button>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.atlas-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 3px;
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    cursor: pointer;
    line-height: 100%;
}

.atlas-btn:hover {
    background-color: var(--hover-bg);
}

.status {
    font-size: 11px;
    color: var(--text-tertiary);
}

.atlas-popup {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 230px;
    padding: 8px 10px;
    font-size: 12px;
    color: var(--text-primary);
}

.title {
    font-size: 13px;
    font-weight: var(--font-weight-semibold);
    margin-bottom: 2px;
}

.row {
    display: flex;
    align-items: center;
    gap: 8px;
}

.grow {
    flex: 1;
}

.muted {
    color: var(--text-tertiary);
}

.warn {
    color: var(--accent-orange);
}

.bar {
    height: 4px;
    border-radius: 2px;
    background: var(--border-color);
    overflow: hidden;
}

.bar > div {
    height: 100%;
    background: var(--primary);
    transition: width 0.2s ease;
}

.generate {
    margin-top: 4px;
    padding: 4px 8px;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-inverse);
    background: var(--primary);
    cursor: pointer;
}

.generate:disabled {
    opacity: 0.6;
    cursor: default;
}
</style>
