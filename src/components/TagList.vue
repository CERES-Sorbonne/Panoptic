<template>
    <div>
      <div class="tag-input">
        <input type="text" v-model="tagInput" @keydown.enter="addTag" placeholder="Add a tag">
      </div>
      <div class="tag-list">
        <tag-badge v-for="tag in tags" :tag="tag" @delete-tag="deleteTag(tag)"/>
      </div>
    </div>
  </template>
  
  <script>
  import TagBadge from './TagBadge.vue';
  
  export default {
    components: {
      TagBadge,
    },
    data() {
      return {
        tags: [],
        tagInput: '',
      };
    },
    methods: {
      addTag() {
        // Créer un nouveau tag
        const newTag = {
          id: generateUniqueId(),
          name: this.tagInput,
        };
        this.tags.push(newTag);
        this.tagInput = '';
      },
      deleteTag(tag) {
        // Supprimer le tag de la liste
        const index = this.tags.indexOf(tag);
        this.tags.splice(index, 1);
      },
    },
  };
  </script>
  
  <style scoped>
  .tag-input {
    margin-top: 1rem;
  }
  .tag-list {
    display: flex;
    flex-wrap: wrap;
    margin-top: 0.5rem;
  }
  </style>