<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePanopticStore } from '@/data/stores/panopticStore'
import Dropdown from '@/components/dropdowns/Dropdown.vue'

const DEFAULT_USER_ID = 'default'

const panoptic = usePanopticStore()
const { t } = useI18n()

const showCreateForm = ref(false)
const newUserName = ref('')
const createError = ref('')

const currentUser = computed(() => panoptic.connectionState?.user)
const isDefault = computed(() => !currentUser.value || currentUser.value.id === DEFAULT_USER_ID)
const displayName = computed(() => isDefault.value ? t('main.home.user.default') : currentUser.value?.name)

const selectableUsers = computed(() =>
    panoptic.users.filter(u => u.id !== currentUser.value?.id && u.id !== DEFAULT_USER_ID)
)

function resetForm() {
    showCreateForm.value = false
    newUserName.value = ''
    createError.value = ''
}

function selectUser(userId: string, hide: () => void) {
    panoptic.connectUser(userId)
    hide()
}

function useDefault(hide: () => void) {
    panoptic.disconnectUser()
    hide()
}

async function submitCreate() {
    const name = newUserName.value.trim()
    if (!name) return
    createError.value = ''
    try {
        await panoptic.createUser(name)
        resetForm()
    } catch {
        createError.value = t('main.home.user.name_taken')
    }
}

async function removeUser(userId: string) {
    await panoptic.deleteUser(userId)
}
</script>

<template>
    <div class="create-option d-flex align-items-center">
        <div class="flex-grow-1">
            <h6 class="create-title m-0">{{ $t('main.home.user.title') }}</h6>
        </div>
        <Dropdown placement="top-end" @hide="resetForm">
            <template #button>
                <div class="user-btn" :title="displayName">
                    <i class="bi bi-person-circle me-1"></i>
                    <span class="user-name">{{ displayName }}</span>
                    <i class="bi bi-chevron-down ms-1 chevron"></i>
                </div>
            </template>
            <template #popup="{ hide }">
                <div class="user-panel text-start p-1">
                    <div v-if="!isDefault" class="user-item bb" @click="useDefault(hide)">
                        <i class="bi bi-person me-2"></i>
                        <span class="flex-grow-1">{{ $t('main.home.user.default') }}</span>
                    </div>
                    <div v-for="user in selectableUsers" :key="user.id" class="user-item bb"
                        @click="selectUser(user.id, hide)">
                        <i class="bi bi-person me-2"></i>
                        <span class="flex-grow-1 text-truncate">{{ user.name }}</span>
                        <i class="bi bi-trash ms-2 delete-btn" :title="$t('main.home.user.delete')"
                            @click.stop="removeUser(user.id)"></i>
                    </div>

                    <div v-if="!isDefault || selectableUsers.length" class="custom-hr mt-1 mb-1" />

                    <div v-if="!showCreateForm" class="user-item bb" @click="showCreateForm = true">
                        <i class="bi bi-plus me-2"></i>
                        {{ $t('main.home.user.new') }}
                    </div>
                    <div v-else class="p-1">
                        <input v-model="newUserName" class="user-input" :placeholder="$t('main.home.user.name_placeholder')"
                            autofocus @keydown.enter.stop="submitCreate" @keydown.escape.stop="resetForm" />
                        <div v-if="createError" class="error-text">{{ createError }}</div>
                        <div class="d-flex justify-content-end gap-1 mt-2">
                            <div class="form-btn" @click="resetForm">{{ $t('main.home.user.cancel') }}</div>
                            <div class="form-btn highlight" @click="submitCreate">{{ $t('main.home.user.create') }}</div>
                        </div>
                    </div>
                </div>
            </template>
        </Dropdown>
    </div>
</template>

<style scoped>
/* Same row layout as the create / import options (Options.vue), pinned at the bottom of HomeView */
.create-option {
    text-align: left;
    padding-bottom: 10px;
    padding-top: 10px;
}

.create-title {
    font-size: 20px;
}

.user-btn {
    display: flex;
    align-items: center;
    height: 36px;
    min-width: 100px;
    max-width: 180px;
    padding: 6px 10px;
    border-radius: 8px;
    background-color: rgb(240, 240, 240);
    color: rgb(45, 45, 45);
    cursor: pointer;
    user-select: none;
}

.user-btn:hover {
    background-color: rgb(227, 227, 255);
    color: black;
}

.user-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.chevron {
    font-size: 11px;
}

.user-panel {
    min-width: 200px;
}

.user-item {
    display: flex;
    align-items: center;
    padding: 4px 6px;
}

.delete-btn {
    opacity: 0;
}

.user-item:hover .delete-btn {
    opacity: 1;
}

.delete-btn:hover {
    color: rgb(200, 60, 60);
}

.user-input {
    width: 100%;
    padding: 4px 8px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 14px;
    outline: none;
}

.user-input:focus {
    border-color: rgb(170, 170, 255);
}

.error-text {
    font-size: 12px;
    color: rgb(200, 60, 60);
    margin-top: 3px;
}

.form-btn {
    padding: 2px 10px;
    border-radius: 8px;
    cursor: pointer;
    background-color: rgb(240, 240, 240);
    color: rgb(45, 45, 45);
}

.form-btn:hover {
    background-color: rgb(227, 227, 255);
}

.form-btn.highlight {
    background-color: rgb(170, 170, 255);
    color: white;
}

.form-btn.highlight:hover {
    background-color: rgb(150, 150, 240);
}
</style>
