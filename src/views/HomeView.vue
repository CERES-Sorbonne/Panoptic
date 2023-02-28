
<script setup>
import ImageList from '../components/ImageList.vue'
import TagBadge from '../components/TagBadge.vue';
import { globalStore } from '../store';
</script>

<template>
  <main>
    <div class="container-fluid h-100">
      <div class="row justify-content-center h-100">
        <div class="col-3 bg-dark">
          <div class="tags-container">
            <tag-badge v-for="(nb, tag) in globalStore.tags" :tag="tag" :number="nb"
              @click="globalStore.addFilter(tag)" />
          </div>
        </div>
        <div class="col-9">
          <ImageList />
        </div>
      </div>
    </div>

  </main>
</template>

<style scoped>
  .tags-container{
    margin-top: 1rem;
  }
</style>