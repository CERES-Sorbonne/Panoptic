<script setup lang="ts">
// Toolbar button that shows the current user. Clicking it opens a list of
// profiles to switch to, including the default profile.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePanopticStore } from '@/data/stores/panopticStore'
import Dropdown from '@/components/dropdowns/Dropdown.vue'
import wTT from '@/components/tooltips/withToolTip.vue'

const DEFAULT_USER_ID = 'default'

const panoptic = usePanopticStore()
const { t } = useI18n()

const currentUser = computed(() => panoptic.connectionState?.user)
const isDefault = computed(() => !currentUser.value || currentUser.value.id === DEFAULT_USER_ID)
const displayName = computed(() => isDefault.value ? t('main.home.user.default') : currentUser.value?.name)

const otherUsers = computed(() =>
    panoptic.users.filter(u => u.id !== currentUser.value?.id && u.id !== DEFAULT_USER_ID)
)

function selectUser(userId: string, hide: () => void) {
    panoptic.connectUser(userId)
    hide()
}

function useDefault(hide: () => void) {
    panoptic.disconnectUser()
    hide()
}
</script>

<template>
    <Dropdown placement="bottom-end" :offset="6" @show="panoptic.fetchUsers()">
        <template #button>
            <wTT message="main.toolbar.profile">
            <div class="profile-btn">
                <i class="bi bi-person-circle"></i>
                <span class="profile-name">{{ displayName }}</span>
                <i class="bi bi-chevron-down profile-chevron"></i>
            </div>
            </wTT>
        </template>
        <template #popup="{ hide }">
            <div class="profile-panel">
                <div class="profile-item current">
                    <i class="bi bi-check2"></i>
                    <span class="profile-item-name">{{ displayName }}</span>
                </div>
                <div v-if="!isDefault" class="profile-item" @click="useDefault(hide)">
                    <i class="bi bi-person"></i>
                    <span class="profile-item-name">{{ $t('main.home.user.default') }}</span>
                </div>
                <div v-for="user in otherUsers" :key="user.id" class="profile-item" @click="selectUser(user.id, hide)">
                    <i class="bi bi-person"></i>
                    <span class="profile-item-name">{{ user.name }}</span>
                </div>
            </div>
        </template>
    </Dropdown>
</template>

<style scoped>
.profile-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    height: 24px;
    max-width: 160px;
    padding: 0 6px;
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-size: 14px;
    cursor: pointer;
    transition: background-color var(--transition-fast);
}

.profile-btn:hover {
    background-color: var(--hover-bg);
}

.profile-name {
    font-size: var(--font-size-sm);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.profile-chevron {
    font-size: 10px;
}

.profile-panel {
    min-width: 180px;
    padding: 4px;
}

.profile-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 6px;
    border-radius: var(--radius-sm);
    font-size: var(--font-size-sm);
    cursor: pointer;
}

.profile-item:hover {
    background-color: var(--hover-bg);
}

.profile-item.current {
    font-weight: var(--font-weight-bold);
    cursor: default;
}

.profile-item.current:hover {
    background: none;
}

.profile-item-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>
