<script setup lang="ts">
import { ModalId } from '@/data/models';
import { ref } from 'vue';
import Modal2 from './Modal2.vue';
import PageWindow from '../utils/PageWindow.vue';
import FileExplorer from './FileExplorer.vue';
import { useDataStore } from '@/data/dataStore';
import { usePanopticStore } from '@/data/panopticStore';
import { projectApi } from '@/data/apiProjectRoutes';
import { t } from '@/locales/i18n';

const data = useDataStore()
const panoptic = usePanopticStore()

enum PAGE {
    Local = 'local',
    Iiif = 'iiif',
}

const options = ref(Object.values(PAGE))
const selectedPage = ref('')

const iiifUrl = ref('')
const iiifSubmitting = ref(false)
const iiifTesting = ref(false)
const iiifTestResult = ref<{
    success: boolean
    title?: string
    label?: string
    version?: number
    itemCount?: number
    error?: string
} | null>(null)
const iiifAuthType = ref<'none' | 'bearer' | 'basic' | 'custom'>('none')
const iiifAuthToken = ref('')
const iiifAuthUsername = ref('')
const iiifAuthPassword = ref('')
const iiifCustomHeaders = ref('')

function close() {
    panoptic.hideModal(ModalId.FILESOURCE)
    selectedPage.value = ''
    iiifUrl.value = ''
    iiifSubmitting.value = false
    iiifTesting.value = false
    iiifTestResult.value = null
    iiifAuthType.value = 'none'
    iiifAuthToken.value = ''
    iiifAuthUsername.value = ''
    iiifAuthPassword.value = ''
    iiifCustomHeaders.value = ''
}

// Local folder import — reuse the existing FileExplorer (emits the chosen path).
async function selectLocalFolder(path: string) {
    if (!path) return
    await data.addFolder(path)
    close()
}

// Test IIIF connection — fetch manifest metadata with optional auth
async function testIiifConnection() {
    const url = iiifUrl.value.trim()
    if (!url || iiifTesting.value) return
    iiifTesting.value = true
    iiifTestResult.value = null
    try {
        const config: any = { url }

        // Add auth config if provided
        if (iiifAuthType.value !== 'none') {
            config.auth = {
                type: iiifAuthType.value,
                token: iiifAuthToken.value,
                username: iiifAuthUsername.value,
                password: iiifAuthPassword.value,
            }
        }

        // Add custom headers if provided
        if (iiifCustomHeaders.value.trim()) {
            try {
                config.headers = JSON.parse(iiifCustomHeaders.value)
            } catch {
                iiifTestResult.value = {
                    success: false,
                    error: t('modals.filesource.error_invalid_headers'),
                }
                iiifTesting.value = false
                return
            }
        }

        const response = await projectApi.post('/iiif/test', config)
        iiifTestResult.value = response.data
    } catch (error: any) {
        iiifTestResult.value = {
            success: false,
            error: error?.response?.data?.error || error?.message || t('modals.filesource.error_network'),
        }
    } finally {
        iiifTesting.value = false
    }
}

// IIIF import — send the manifest/collection URL with optional auth to the backend.
async function importIiif() {
    const url = iiifUrl.value.trim()
    if (!url || iiifSubmitting.value || !iiifTestResult.value?.success) return
    iiifSubmitting.value = true
    try {
        const config: any = { url }

        // Add auth config if provided
        if (iiifAuthType.value !== 'none') {
            config.auth = {
                type: iiifAuthType.value,
                token: iiifAuthToken.value,
                username: iiifAuthUsername.value,
                password: iiifAuthPassword.value,
            }
        }

        // Add custom headers if provided
        if (iiifCustomHeaders.value.trim()) {
            config.headers = JSON.parse(iiifCustomHeaders.value)
        }

        // Use the config for import
        await projectApi.post('/import/iiif', config)
        close()
    } catch (error: any) {
        alert(error?.response?.data?.detail || error?.message || t('modals.filesource.error_import'))
    } finally {
        iiifSubmitting.value = false
    }
}
</script>

<template>
    <Modal2 :id="ModalId.FILESOURCE">
        <template #title>
            {{ $t('modals.filesource.title') }}
        </template>
        <template #content>
            <div class="h-100 overflow-hidden">
                <PageWindow :options="options" v-model:page="selectedPage" hide-menu>

                    <template #default="{ page }">
                        <!-- Home: choose the source type -->
                        <div v-if="page == ''" class="source-home">
                            <div class="source-card" @click="selectedPage = PAGE.Local">
                                <i class="bi bi-folder source-icon" />
                                <div class="source-label">{{ $t('modals.filesource.local') }}</div>
                            </div>
                            <div class="source-card" @click="selectedPage = PAGE.Iiif">
                                <i class="bi bi-globe2 source-icon" />
                                <div class="source-label">{{ $t('modals.filesource.iiif') }}</div>
                            </div>
                        </div>

                        <!-- Local folder: reuse the file explorer from the import modal -->
                        <FileExplorer v-if="page == PAGE.Local" mode="images" @select="selectLocalFolder" />

                        <!-- IIIF: manifest / collection URL -->
                        <div v-if="page == PAGE.Iiif" class="iiif-page">
                            <div class="iiif-body">
                                <div class="field">
                                    <label class="field-label">{{ $t('modals.filesource.iiif_url_label') }}</label>
                                    <input v-model="iiifUrl" type="url" class="fs-input url-input"
                                        placeholder="https://.../manifest.json" @keydown.enter="testIiifConnection" />
                                    <div class="field-hint">{{ $t('modals.filesource.iiif_url_hint') }}</div>
                                    <div class="actions">
                                        <div class="action" :class="{ disabled: !iiifUrl.trim() || iiifTesting || iiifSubmitting }"
                                            @click="testIiifConnection">
                                            <span v-if="iiifTesting" class="spinner-border spinner-border-sm me-1" role="status" />
                                            <i v-else class="bi bi-arrow-repeat me-1" />
                                            {{ $t('modals.filesource.test_connection') }}
                                        </div>
                                        <div class="action primary"
                                            :class="{ disabled: !iiifUrl.trim() || iiifSubmitting || !iiifTestResult?.success }"
                                            @click="importIiif">
                                            <span v-if="iiifSubmitting" class="spinner-border spinner-border-sm me-1" role="status" />
                                            {{ $t('modals.filesource.import') }}
                                        </div>
                                    </div>
                                </div>

                                <!-- Test result -->
                                <div v-if="iiifTestResult" class="result" :class="iiifTestResult.success ? 'ok' : 'ko'">
                                    <i :class="iiifTestResult.success ? 'bi bi-check-circle' : 'bi bi-exclamation-circle'"
                                        class="result-icon" />
                                    <div class="result-body">
                                        <div class="result-title">
                                            {{ iiifTestResult.success ? $t('modals.filesource.test_success') : $t('modals.filesource.test_failed') }}
                                        </div>
                                        <template v-if="iiifTestResult.success">
                                            <div v-if="iiifTestResult.label || iiifTestResult.title" class="result-line">
                                                <span class="result-key">{{ $t('modals.filesource.result_title') }}</span>
                                                {{ iiifTestResult.label || iiifTestResult.title }}
                                            </div>
                                            <div v-if="iiifTestResult.version" class="result-line">
                                                <span class="result-key">{{ $t('modals.filesource.result_version') }}</span>
                                                v{{ iiifTestResult.version }}
                                            </div>
                                            <div v-if="iiifTestResult.itemCount !== undefined" class="result-line">
                                                <span class="result-key">{{ $t('modals.filesource.result_items') }}</span>
                                                {{ iiifTestResult.itemCount }}
                                            </div>
                                        </template>
                                        <div v-else class="result-line">{{ iiifTestResult.error }}</div>
                                    </div>
                                </div>

                                <!-- Authentication options (show if test succeeded) -->
                                <div v-if="iiifTestResult?.success" class="section">
                                    <div class="section-title">
                                        <i class="bi bi-lock" />
                                        {{ $t('modals.filesource.auth_section') }}
                                    </div>

                                    <div class="field">
                                        <label class="field-label">{{ $t('modals.filesource.auth_type') }}</label>
                                        <select v-model="iiifAuthType" class="fs-input">
                                            <option value="none">{{ $t('modals.filesource.auth_none') }}</option>
                                            <option value="bearer">{{ $t('modals.filesource.auth_bearer') }}</option>
                                            <option value="basic">{{ $t('modals.filesource.auth_basic') }}</option>
                                            <option value="custom">{{ $t('modals.filesource.auth_custom') }}</option>
                                        </select>
                                    </div>

                                    <!-- Bearer Token -->
                                    <div v-if="iiifAuthType === 'bearer'" class="field">
                                        <label class="field-label">{{ $t('modals.filesource.token_label') }}</label>
                                        <input v-model="iiifAuthToken" type="password" class="fs-input"
                                            :placeholder="$t('modals.filesource.token_placeholder')" />
                                        <div class="field-hint mono">{{ $t('modals.filesource.token_hint') }}</div>
                                    </div>

                                    <!-- Basic Auth -->
                                    <template v-if="iiifAuthType === 'basic'">
                                        <div class="field">
                                            <label class="field-label">{{ $t('modals.filesource.username') }}</label>
                                            <input v-model="iiifAuthUsername" type="text" class="fs-input" />
                                        </div>
                                        <div class="field">
                                            <label class="field-label">{{ $t('modals.filesource.password') }}</label>
                                            <input v-model="iiifAuthPassword" type="password" class="fs-input" />
                                            <div class="field-hint mono">{{ $t('modals.filesource.basic_hint') }}</div>
                                        </div>
                                    </template>

                                    <!-- Custom Header -->
                                    <div v-if="iiifAuthType === 'custom'" class="field">
                                        <label class="field-label">{{ $t('modals.filesource.api_key') }}</label>
                                        <input v-model="iiifAuthToken" type="password" class="fs-input"
                                            :placeholder="$t('modals.filesource.token_placeholder')" />
                                        <div class="field-hint mono">{{ $t('modals.filesource.api_key_hint') }}</div>
                                    </div>

                                    <!-- Custom Headers -->
                                    <div class="field">
                                        <label class="field-label">
                                            {{ $t('modals.filesource.headers_label') }}
                                            <span class="tag">{{ $t('modals.filesource.optional') }}</span>
                                        </label>
                                        <textarea v-model="iiifCustomHeaders" class="fs-input mono" rows="3"
                                            placeholder='{"X-Custom": "value", "Accept-Language": "en"}' />
                                        <div class="field-hint">{{ $t('modals.filesource.headers_hint') }}</div>
                                    </div>
                                </div>
                            </div>

                        </div>

                    </template>
                </PageWindow>
            </div>
        </template>
    </Modal2>
</template>

<style scoped>
.source-home {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-lg);
    height: 100%;
}

.source-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--spacing-sm);
    width: 140px;
    height: 140px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background-color: var(--bg-secondary);
    color: var(--text-secondary);
    cursor: pointer;
    transition: background-color var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
}

.source-card:hover {
    background-color: var(--primary-light);
    border-color: var(--primary);
    color: var(--primary);
}

.source-icon {
    font-size: 46px;
}

.source-label {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
}

/* ── IIIF page: scrollable form + pinned action bar ──────────────────── */
.iiif-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    background-color: var(--island-surface);
    color: var(--text-primary);
    font-size: var(--font-size-sm);
}

.iiif-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: var(--spacing-lg);
    /* keep the form as a readable column instead of stretching modal-wide */
    max-width: 620px;
}

.field {
    margin-bottom: var(--spacing-md);
}

.field-label {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
    color: var(--text-secondary);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    text-transform: uppercase;
    letter-spacing: 0.02em;
}

.fs-input {
    width: 100%;
    box-sizing: border-box;
    padding: 8px 10px;
    color: var(--text-primary);
    background-color: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    font-family: inherit;
    outline: none;
    transition: border-color var(--transition-fast);
}

.fs-input:focus {
    border-color: var(--focus-ring);
}

/* The URL is the primary input of this page */
.url-input {
    padding: 10px 12px;
    font-size: var(--font-size-base);
}

.field-hint {
    margin-top: 4px;
    color: var(--text-tertiary);
    font-size: var(--font-size-xs);
}

.mono {
    font-family: var(--font-mono);
}

textarea.fs-input {
    resize: vertical;
    line-height: var(--line-height-normal);
}

select.fs-input {
    height: auto;
    cursor: pointer;
}

.tag {
    padding: 1px 5px;
    border-radius: var(--radius-sm);
    background-color: var(--bg-tertiary);
    color: var(--text-tertiary);
    font-size: 10px;
    font-weight: var(--font-weight-medium);
    text-transform: none;
    letter-spacing: 0;
}

/* Connection test feedback */
.result {
    display: flex;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm) var(--spacing-md);
    margin-bottom: var(--spacing-md);
    border: 1px solid var(--border-color);
    border-left-width: 3px;
    border-radius: var(--radius-sm);
    background-color: var(--bg-secondary);
}

.result.ok {
    border-left-color: var(--success);
}

.result.ko {
    border-left-color: var(--error);
}

.result-icon {
    line-height: 1.4;
}

.result.ok .result-icon {
    color: var(--success);
}

.result.ko .result-icon {
    color: var(--error);
}

.result-title {
    font-weight: var(--font-weight-semibold);
}

.result-line {
    margin-top: 2px;
    color: var(--text-secondary);
    font-size: var(--font-size-xs);
}

.result-key {
    color: var(--text-tertiary);
    margin-right: 4px;
}

.section {
    padding: var(--spacing-md);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background-color: var(--bg-secondary);
}

.section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: var(--spacing-sm);
    color: var(--text-secondary);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    text-transform: uppercase;
    letter-spacing: 0.02em;
}

/* Buttons sit right under the URL field they act on */
.actions {
    display: flex;
    gap: var(--spacing-sm);
    margin-top: var(--spacing-sm);
}

.action {
    display: flex;
    align-items: center;
    padding: 6px 14px;
    cursor: pointer;
    color: var(--text-secondary);
    background-color: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    font-weight: var(--font-weight-medium);
    transition: background-color var(--transition-fast);
}

.action:hover {
    background-color: var(--hover-bg);
    color: var(--text-primary);
}

.action.primary {
    background-color: var(--primary);
    border-color: var(--primary);
    color: var(--text-inverse);
}

.action.primary:hover {
    background-color: var(--primary-dark);
    color: var(--text-inverse);
}

.action.disabled {
    pointer-events: none;
    color: var(--disabled-text);
    background-color: var(--disabled-bg);
    border-color: var(--border-light);
}

</style>
