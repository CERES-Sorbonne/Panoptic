<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ImageType } from '@/data/models'
import { apiGetImageTypes, apiUpsertImageType, apiDeleteImageType, apiGetImageStats } from '@/data/apiProjectRoutes'
import SectionDivider from '../utils/SectionDivider.vue'

const FORMATS = ['jpeg', 'webp', 'png']

const imageTypes = ref<ImageType[]>([])
const counts = ref<{ [typeId: number]: number }>({})
const sha1Count = ref(0)

const showCreate = ref(false)
const newType = reactive({ name: '', format: 'jpeg', size: 256, autoGen: true })

async function load() {
    const [types, stats] = await Promise.all([apiGetImageTypes(), apiGetImageStats()])
    imageTypes.value = types
    counts.value = stats.counts
    sha1Count.value = stats.sha1Count
}

async function deleteType(id: number) {
    await apiDeleteImageType(id)
    await load()
}

async function toggleAutoGen(type: ImageType) {
    await apiUpsertImageType({ ...type, autoGen: !type.autoGen })
    await load()
}

async function createType() {
    if (!newType.name.trim()) return
    await apiUpsertImageType({
        id: -1,
        name: newType.name.trim(),
        format: newType.format,
        width: newType.size || null,
        height: newType.size || null,
        autoGen: newType.autoGen,
    })
    Object.assign(newType, { name: '', format: 'jpeg', size: 256, autoGen: true })
    showCreate.value = false
    await load()
}

onMounted(load)
</script>

<template>
    <div class="main">
        <SectionDivider>{{ $t('modals.settings.thumbnailStorage') }}</SectionDivider>
        <table>
            <thead>
                <tr>
                    <th></th>
                    <th>Name</th>
                    <th>Format</th>
                    <th>Size</th>
                    <th title="Generate on import">Auto</th>
                    <th>Stored</th>
                </tr>
            </thead>
            <tbody>
                <tr v-for="type in imageTypes" :key="type.id">
                    <td><i class="bb bi bi-x" @click="deleteType(type.id)" /></td>
                    <td>{{ type.name }}</td>
                    <td>{{ type.format }}</td>
                    <td>{{ type.width ?? '∞' }} px</td>
                    <td>
                        <input type="checkbox" :checked="type.autoGen" @change="toggleAutoGen(type)" />
                    </td>
                    <td>
                        <span v-if="counts[type.id] != undefined">{{ counts[type.id] }} / {{ sha1Count }}</span>
                        <span v-else>0 / {{ sha1Count }}</span>
                    </td>
                </tr>
            </tbody>
        </table>

        <div v-if="!showCreate">
            <span class="bb" @click="showCreate = true">{{ $t('modals.settings.createNewImageType') }} <i class="bi bi-plus" /></span>
        </div>

        <SectionDivider v-if="showCreate">
            <span style="margin-left: 3px;">{{ $t('modals.settings.createNewImageType') }}</span>
        </SectionDivider>
        <div v-if="showCreate" style="font-size: 15px;">
            <table>
                <tbody>
                    <tr>
                        <td>{{ $t('modals.settings.name') }}</td>
                        <td><input type="text" v-model="newType.name" @keydown.enter="createType" @keydown.escape="showCreate = false" /></td>
                    </tr>
                    <tr>
                        <td>{{ $t('modals.settings.format') }}</td>
                        <td>
                            <select v-model="newType.format">
                                <option v-for="f in FORMATS" :key="f" :value="f">{{ f }}</option>
                            </select>
                        </td>
                    </tr>
                    <tr>
                        <td>{{ $t('modals.settings.maxSize') }}</td>
                        <td><input type="number" step="1" v-model.number="newType.size" min="1" /></td>
                    </tr>
                    <tr>
                        <td>{{ $t('modals.settings.autoOnImport') }}</td>
                        <td><input type="checkbox" v-model="newType.autoGen" /></td>
                    </tr>
                </tbody>
            </table>
            <div class="ms-3 mt-3">
                <SectionDivider>
                    <span class="bbb me-2" @click="showCreate = false">{{ $t('modals.settings.cancel') }}</span>
                    <span class="bbb" @click="createType">{{ $t('modals.settings.create') }}</span>
                </SectionDivider>
            </div>
        </div>
    </div>
</template>

<style scoped>
.main {
    padding: 5px;
}

table {
    border-collapse: separate;
    border-spacing: 16px 0;
    margin-bottom: 8px;
}

input[type="text"],
input[type="number"] {
    font-size: 14px;
    line-height: 12px;
    padding: 2px 4px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
}

select {
    font-size: 14px;
    padding: 2px 4px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
}
</style>
