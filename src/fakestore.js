import { computed, reactive } from 'vue'
import { apiGetImages, apiAddTag, apiRemoveTag, SERVER_PREFIX } from './utils/api'

function saveTabState(store) {
  localStorage.setItem('tabs', JSON.stringify(store.tabs))
  localStorage.setItem('selectedTabName', store.selectedTabName)
}

function loadTabState(store) {
  try {
    let tabs = JSON.parse(localStorage.getItem('tabs'))
    let selectedTabName = localStorage.getItem('selectedTabName')

    if(tabs) {
      store.tabs = tabs
    }
    if(selectedTabName) {
      store.selectTab(selectedTabName)
    }
  }
  catch {
    // ignore
  }
}


export const fakeStore = reactive({
  images: [],
  properties: [
    {name: 'category1' ,type: 'tag'}
  ],
  options: {
    display: ['grid', 'list','3eme Oeil'],
    filter: ['filter1', 'filter2', 'filter3', 'other1', 'other2', 'toto', 'felix', 'darmanin'],
    groupBy: ['filter1', 'filter2', 'toto', 'darmanin']
  },
  tabs: [
  ],
  selectedTabName: '',
  addTab(tabName) {
    this.tabs.push({
      name: tabName,
      state: {
        display: 'grid',
        filter: [],
        groupBy: [],
      },
      groups: [{name: 'all', images: 34}]
    })
    this.saveTabState(this)
  },
  removeTab(tabName) {
    let index = this.tabs.findIndex(t => t.name == tabName)
    if(index < 0) {
      return
    }
    this.tabs.splice(index, 1)
    this.saveTabState(this)
  },
  selectTab(tabName) {
    this.selectedTabName = tabName
    this.saveTabState(this)
  },
  saveTabState() {
    localStorage.setItem('tabs', JSON.stringify(this.tabs))
    localStorage.setItem('selectedTabName', this.selectedTabName)
  }
})

loadTabState(fakeStore)