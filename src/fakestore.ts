import { reactive } from 'vue'


export const fakeStore = reactive({
  images: [],
  properties: [
    {
      id: 0, 
      name: 'Classification' ,
      type: 'multi-tag', 
      values: { 
        shape: { rectangle: undefined, square: undefined, circle: undefined},
        colors: { blue: undefined, green: undefined}
      },
      selected: []
    }
  ],
  selected: {},
  options: {
    display: ['grid', 'list','3eme Oeil'],
    filter: ['filter1', 'filter2', 'filter3', 'other1', 'other2', 'toto', 'felix', 'darmanin'],
    groupBy: ['filter1', 'filter2', 'toto', 'darmanin']
  },
  tabs: [
  ],
  selectedTabName: '',
  addTab(tabName: string) {
    this.tabs.push({
      name: tabName,
      state: {
        display: 'grid',
        filter: [],
        groupBy: [],
      },
      groups: [{name: 'all', images: 34}],
    })
    this.saveTabState()
  },
  removeTab(tabName: string) {
    let index = this.tabs.findIndex(t => t.name == tabName)
    if(index < 0) {
      return
    }
    this.tabs.splice(index, 1)
    this.saveTabState()
  },
  selectTab(tabName: string) {
    this.selectedTabName = tabName
    this.saveTabState()
  },
  saveTabState() {
    localStorage.setItem('tabs', JSON.stringify(this.tabs))
    localStorage.setItem('selectedTabName', this.selectedTabName)
  },
  loadTabState() {
    try {
      let tabs = JSON.parse(localStorage.getItem('tabs'))
      let selectedTabName = localStorage.getItem('selectedTabName')
  
      if(tabs) {
        this.tabs = tabs
      }
      if(selectedTabName) {
        this.selectTab(selectedTabName)
      }
    }
    catch {
      // ignore
    }
  }
})

fakeStore.loadTabState()