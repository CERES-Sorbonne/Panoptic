<script setup lang="ts">
import { computed, ref } from 'vue'
import { usePanopticStore } from '@/data/panopticStore'

const DEFAULT_USER_ID = 'default'

const panoptic = usePanopticStore()

const expanded = ref(false)
const showCreateForm = ref(false)
const newUserName = ref('')
const createError = ref('')

const currentUser = computed(() => panoptic.connectionState?.user)
const isDefault = computed(() => !currentUser.value || currentUser.value.id === DEFAULT_USER_ID)
const displayName = computed(() => isDefault.value ? 'Default' : currentUser.value?.name)

const selectableUsers = computed(() =>
    panoptic.users.filter(u => u.id !== currentUser.value?.id && u.id !== DEFAULT_USER_ID)
)

function toggle() {
    expanded.value = !expanded.value
    if (!expanded.value) {
        showCreateForm.value = false
        newUserName.value = ''
        createError.value = ''
    }
}

function selectUser(userId: string) {
    panoptic.connectUser(userId)
    expanded.value = false
}

function useDefault() {
    panoptic.disconnectUser()
    expanded.value = false
}

async function submitCreate() {
    const name = newUserName.value.trim()
    if (!name) return
    createError.value = ''
    try {
        await panoptic.createUser(name)
        newUserName.value = ''
        showCreateForm.value = false
    } catch {
        createError.value = 'Name already taken'
    }
}

async function removeUser(userId: string, e: Event) {
    e.stopPropagation()
    await panoptic.deleteUser(userId)
}
</script>

<template>
    <div class="user-selector">
        <div class="user-current bb" @click="toggle">
            <i class="bi bi-person-circle me-2"></i>
            <span class="user-name">{{ displayName }}</span>
            <i class="bi ms-auto" :class="expanded ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
        </div>

        <div v-if="expanded" class="user-panel">
            <div v-if="!isDefault" class="user-item bb dimmed" @click="useDefault">
                <i class="bi bi-person me-2"></i>
                Default
            </div>

            <div
                v-for="user in selectableUsers"
                :key="user.id"
                class="user-item bb d-flex align-items-center"
                @click="selectUser(user.id)"
            >
                <i class="bi bi-person me-2"></i>
                <span class="flex-grow-1">{{ user.name }}</span>
                <i
                    class="bi bi-x ms-2 delete-btn"
                    @click="removeUser(user.id, $event)"
                ></i>
            </div>

            <div v-if="!showCreateForm" class="user-item bb add-user" @click="showCreateForm = true">
                <i class="bi bi-plus me-1"></i>
                New user
            </div>

            <div v-else class="create-form">
                <input
                    v-model="newUserName"
                    class="user-input"
                    placeholder="Name"
                    autofocus
                    @keydown.enter="submitCreate"
                    @keydown.escape="showCreateForm = false"
                />
                <div v-if="createError" class="error-text">{{ createError }}</div>
                <div class="d-flex gap-1 mt-1">
                    <div class="form-btn confirm" @click="submitCreate">Create</div>
                    <div class="form-btn" @click="showCreateForm = false; newUserName = ''">Cancel</div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.user-selector {
    width: 100%;
}

.user-current {
    display: flex;
    align-items: center;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    color: rgb(60, 60, 60);
    user-select: none;
}

.user-current:hover {
    background-color: rgb(232, 232, 255);
}

.user-name {
    font-weight: 500;
}

.user-panel {
    margin-top: 4px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    background: white;
}

.user-item {
    display: flex;
    align-items: center;
    padding: 7px 10px;
    font-size: 13px;
    cursor: pointer;
    color: rgb(50, 50, 50);
}

.user-item:hover {
    background-color: rgb(232, 232, 255);
}

.user-item:not(:last-child) {
    border-bottom: 1px solid var(--border-color);
}

.dimmed {
    color: rgb(120, 120, 120);
}

.add-user {
    color: rgb(100, 100, 200);
}

.delete-btn {
    opacity: 0;
    color: rgb(180, 60, 60);
    font-size: 15px;
}

.user-item:hover .delete-btn {
    opacity: 1;
}

.create-form {
    padding: 8px;
    border-top: 1px solid var(--border-color);
}

.user-input {
    width: 100%;
    padding: 4px 8px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 13px;
    outline: none;
}

.user-input:focus {
    border-color: rgb(150, 150, 220);
}

.error-text {
    font-size: 12px;
    color: rgb(200, 60, 60);
    margin-top: 3px;
}

.form-btn {
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    background: rgb(240, 240, 240);
    color: rgb(50, 50, 50);
}

.form-btn:hover {
    background: rgb(225, 225, 225);
}

.form-btn.confirm {
    background: rgb(170, 170, 255);
    color: white;
}

.form-btn.confirm:hover {
    background: rgb(140, 140, 230);
}
</style>
