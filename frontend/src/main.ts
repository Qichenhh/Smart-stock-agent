import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'
import Home from './views/Home.vue'
import Result from './views/Result.vue'
import Compare from './views/Compare.vue'
import SectorHeat from './views/SectorHeat.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Home', component: Home },
    { path: '/result', name: 'Result', component: Result },
    { path: '/compare', name: 'Compare', component: Compare },
    { path: '/sectors', name: 'SectorHeat', component: SectorHeat },
  ]
})

const app = createApp(App)
app.use(router)
app.use(Antd)
app.mount('#app')
