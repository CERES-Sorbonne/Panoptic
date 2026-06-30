<script setup lang="ts">
import { ModalId } from '@/data/models';
import { ref } from 'vue';
import Modal2 from './Modal2.vue';
import PageWindow from '../utils/PageWindow.vue';
import FileExplorer from './FileExplorer.vue';
import { useDataStore } from '@/data/dataStore';
import { usePanopticStore } from '@/data/panopticStore';
import { projectApi } from '@/data/apiProjectRoutes';

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
                    error: 'Invalid JSON in custom headers field',
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
            error: error?.response?.data?.error || error?.message || 'Network error or server unavailable',
        }
    } finally {
        iiifTesting.value = false
    }
}

// IIIF import — send the manifest/collection URL with optional auth to the backend.
async function importIiif() {
    const url = iiifUrl.value.trim()
    if (!url || iiifSubmitting.value) return
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
        alert(error?.response?.data?.detail || error?.message || 'Import failed')
    } finally {
        iiifSubmitting.value = false
    }
}
</script>

<template>
    <Modal2 :id="ModalId.FILESOURCE">
        <template #title>
            Add file source
        </template>
        <template #content>
            <div class="h-100 overflow-hidden">
                <PageWindow :options="options" v-model:page="selectedPage">

                    <template #default="{ page }">
                        <!-- Home: choose the source type -->
                        <div v-if="page == ''" class="source-home">
                            <div class="source-card" @click="selectedPage = PAGE.Local">
                                <i class="bi bi-folder source-icon" />
                                <div class="source-label">Local folder</div>
                            </div>
                            <div class="source-card" @click="selectedPage = PAGE.Iiif">
                                <i class="bi bi-globe2 source-icon" />
                                <div class="source-label">IIIF</div>
                            </div>
                        </div>

                        <!-- Local folder: reuse the file explorer from the import modal -->
                        <FileExplorer v-if="page == PAGE.Local" mode="images" @select="selectLocalFolder" />

                        <!-- IIIF: manifest / collection URL -->
                        <div v-if="page == PAGE.Iiif" class="p-4">
                            <label class="form-label">IIIF Manifest or Collection URL</label>
                            <input v-model="iiifUrl" type="url" class="form-control"
                                placeholder="https://.../manifest.json"
                                @keydown.enter="testIiifConnection" />
                            <div class="text-secondary mt-2" style="font-size: 12px;">
                                Paste a IIIF Presentation API manifest or collection URL (v2 or v3).
                            </div>

                            <!-- Test result alert -->
                            <div v-if="iiifTestResult" :class="['alert mt-3', iiifTestResult.success ? 'alert-success' : 'alert-danger']">
                                <div v-if="iiifTestResult.success" class="alert-content">
                                    <i class="bi bi-check-circle me-2" />
                                    <strong>Connection successful!</strong>
                                    <div class="mt-2 ms-4">
                                        <div v-if="iiifTestResult.label || iiifTestResult.title" class="mb-1">
                                            <strong>Title:</strong> {{ iiifTestResult.label || iiifTestResult.title }}
                                        </div>
                                        <div v-if="iiifTestResult.version" class="mb-1">
                                            <strong>IIIF Version:</strong> v{{ iiifTestResult.version }}
                                        </div>
                                        <div v-if="iiifTestResult.itemCount !== undefined" class="mb-1">
                                            <strong>Items:</strong> {{ iiifTestResult.itemCount }}
                                        </div>
                                    </div>
                                </div>
                                <div v-else class="alert-content">
                                    <i class="bi bi-exclamation-circle me-2" />
                                    <strong>Connection failed:</strong>
                                    <div class="mt-2 ms-4">
                                        {{ iiifTestResult.error }}
                                    </div>
                                </div>
                            </div>

                            <!-- Authentication options (show if test succeeded) -->
                            <div v-if="iiifTestResult?.success" class="mt-4">
                                <div class="form-section">
                                    <label class="form-label d-flex align-items-center">
                                        <i class="bi bi-lock me-2" />
                                        Authentication (Optional)
                                    </label>

                                    <div class="mb-3">
                                        <label class="form-label">Auth Type</label>
                                        <select v-model="iiifAuthType" class="form-select form-select-sm">
                                            <option value="none">None</option>
                                            <option value="bearer">Bearer Token</option>
                                            <option value="basic">Basic Auth</option>
                                            <option value="custom">Custom Header (X-API-Key)</option>
                                        </select>
                                    </div>

                                    <!-- Bearer Token -->
                                    <div v-if="iiifAuthType === 'bearer'" class="mb-3">
                                        <label class="form-label">API Key / Token</label>
                                        <input v-model="iiifAuthToken" type="password" class="form-control form-control-sm"
                                            placeholder="your-api-key" />
                                        <small class="text-muted">Sent as: Authorization: Bearer &lt;token&gt;</small>
                                    </div>

                                    <!-- Basic Auth -->
                                    <div v-if="iiifAuthType === 'basic'">
                                        <div class="mb-3">
                                            <label class="form-label">Username</label>
                                            <input v-model="iiifAuthUsername" type="text" class="form-control form-control-sm" />
                                        </div>
                                        <div class="mb-3">
                                            <label class="form-label">Password</label>
                                            <input v-model="iiifAuthPassword" type="password" class="form-control form-control-sm" />
                                        </div>
                                        <small class="text-muted">Sent as: Authorization: Basic &lt;base64(user:pass)&gt;</small>
                                    </div>

                                    <!-- Custom Header -->
                                    <div v-if="iiifAuthType === 'custom'" class="mb-3">
                                        <label class="form-label">API Key</label>
                                        <input v-model="iiifAuthToken" type="password" class="form-control form-control-sm"
                                            placeholder="your-api-key" />
                                        <small class="text-muted">Sent as: X-API-Key: &lt;key&gt;</small>
                                    </div>

                                    <!-- Custom Headers -->
                                    <div class="mb-3">
                                        <label class="form-label d-flex align-items-center">
                                            Custom Headers (JSON)
                                            <span class="badge bg-secondary ms-2">Optional</span>
                                        </label>
                                        <textarea v-model="iiifCustomHeaders" class="form-control form-control-sm"
                                            placeholder='{"X-Custom": "value", "Accept-Language": "en"}'
                                            rows="3" />
                                        <small class="text-muted">Additional HTTP headers as JSON object</small>
                                    </div>
                                </div>
                            </div>

                            <!-- Action buttons -->
                            <div class="d-flex justify-content-end gap-2 mt-3">
                                <button class="btn btn-outline-secondary"
                                    :disabled="!iiifUrl.trim() || iiifTesting || iiifSubmitting"
                                    @click="testIiifConnection">
                                    <span v-if="iiifTesting" class="spinner-border spinner-border-sm me-1"
                                        role="status" />
                                    <i v-else class="bi bi-arrow-repeat me-1" />
                                    Test Connection
                                </button>
                                <button class="btn btn-primary"
                                    :disabled="!iiifUrl.trim() || iiifSubmitting || !iiifTestResult?.success"
                                    @click="importIiif">
                                    <span v-if="iiifSubmitting" class="spinner-border spinner-border-sm me-1"
                                        role="status" />
                                    Import
                                </button>
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

.alert {
    border: 1px solid;
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
    font-size: 14px;
}

.alert-success {
    background-color: #d4edda;
    border-color: #c3e6cb;
    color: #155724;
}

.alert-danger {
    background-color: #f8d7da;
    border-color: #f5c6cb;
    color: #721c24;
}

.alert-content {
    display: flex;
    align-items: flex-start;
}

.form-section {
    padding: var(--spacing-md);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background-color: var(--bg-secondary);
}

.form-section .form-label {
    font-weight: var(--font-weight-medium);
    font-size: var(--font-size-sm);
    margin-bottom: var(--spacing-sm);
}
</style>
