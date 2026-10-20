import { createApp } from 'vue'
import App from './App.vue'
import { bootstrapRuntime } from './nativeRuntime'
import { exportNotesArchive, importNotesArchive } from './notesArchive'
import './style.css'
import './study-design.css'

window.framewiseExportNotes = exportNotesArchive
window.framewiseImportNotes = importNotesArchive

void bootstrapRuntime(window.framewiseDesktop).finally(() => createApp(App).mount('#app'))
