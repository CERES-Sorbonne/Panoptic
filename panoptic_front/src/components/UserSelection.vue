<script setup lang="ts">
import { defineProps, defineEmits } from 'vue'

export interface User {
  id: number
  name: string
}

export interface UserState extends User {
  connectedTo?: string
}

const props = defineProps<{
  users: UserState[]
}>()

const emits = defineEmits<{
  (e: 'connectUser', user: UserState): void
}>()

function handleClick(user: UserState) {
  if (!user.connectedTo) {
    emits('connectUser', user)
  }
}
</script>

<template>
  <div class="user-block">
    <div class="mt-5 mb-5">Server Mode: Select a profile</div>
    <div
      v-for="user in users"
      :key="user.id"
      :class="['user-entry', { bb: !user.connectedTo }]"
      @click="handleClick(user)"
    >
      <span>{{ user.name }}</span>
      <span style="margin-left: 0.5em; color: gray">
        ({{ user.connectedTo ? 'Connected' : 'Available' }})
      </span>
    </div>
  </div>
</template>

<style scoped>
.user-entry {
  cursor: pointer;
  padding: 0.5em;
}

.user-entry:not(.bb) {
  cursor: default;
  color: #888;
}

.user-block {
    width: 300px;
    margin: auto;
    height: 500px;
}
</style>
