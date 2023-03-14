<template>
  <div>
    <h4>
      {{ image.name }}
    </h4>
    <div class="tag-input" ref="tagInputContainer">
      <!-- <input type="text" v-model="tagInput" @keydown.enter="addTag" placeholder="Add a tag" @focusout="showTagList = false" @focus="showTagList = true" style="width: 100%"> -->
      <input type="text" v-model="tagInput" @keydown.enter="addTag" placeholder="Add a tag"  @focus="showTagList = true" style="width: 100%">
      <ul v-if="showTagList && filteredTagList.length > 0" class="tag-proposals" ref="tagProposals">
        <li v-for="tag in filteredTagList">
          <tag-badge :tag="tag" @delete-tag="deleteTag(tag)" @click="globalStore.addTag(image, tag)"/>
        </li>
      </ul>
    </div>
    <div class="tag-list">
      <tag-badge v-for="tag in image.tags" :tag="tag" @delete-tag="deleteTag(tag)"/>
    </div>
  </div>
</template>

<script setup>
import TagBadge from '../TagTree/TagBadge.vue';

import {ref, computed, onMounted, onUnmounted} from 'vue'

import {globalStore} from '../../data/store'

const addTag = async () => {
  await globalStore.addTag(props.image, tagInput.value)
  tagInput.value = ""
}

const props = defineProps({
  image: Object
})

const tagInput = ref('');
const showTagList = ref(false);

const filteredTagList = computed(() => {
  let filtered = Object.keys(globalStore.tags).filter(tag => !props.image.tags.includes(tag.toLowerCase()) && tag.toLowerCase().includes(tagInput.value.toLowerCase()));
  return filtered.length === 0 && tagInput.value.trim() !== "" ? [tagInput.value] : filtered
})

// Ferme la liste de propositions si le clic est effectué en dehors de la liste ou de l'input
const handleContainerClick = (event) => {
  if (!tagProposals.value.contains(event.target) && !tagInputContainer.value.contains(event.target)) {
    showTagList.value = false;
  }
};

const tagInputContainer = ref(null);
const tagProposals = ref(null);

onMounted(() => {
  document.addEventListener('click', handleContainerClick);
});

onUnmounted(() => {
  document.removeEventListener('click', handleContainerClick);
});

</script>

<style scoped>
.tag-input {
  margin-top: 1rem;
  position: relative;
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}
.tag-list > * {
  margin-right: 0.5rem;
  margin-bottom: 0.5rem;
}

.tag-proposals {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 10;
  background-color: white;
  border: 1px solid gray;
  border-top: none;
  border-radius: 0 0 0.5rem 0.5rem;
  padding: 0.5rem;
  max-height: 120px;
  overflow-y: auto;
}

</style>