<script setup lang="ts">
defineProps<{ name: string }>()
const paths: Record<string, string> = {
  play: 'M9 5l11 7-11 7V5Z',
  upload: 'M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5',
  map: 'M4 12h6m0 0V5h8m-8 7v7h8M2 10h4v4H2zm16-7h4v4h-4zm0 14h4v4h-4z',
  transcript: 'M5 3h14v18H5zM8 8h8M8 12h8M8 16h5',
  slides: 'M3 4h18v13H3zM12 17v4m-4 0h8M7 13l3-4 3 2 4-5',
  notes: 'M16 3l5 5-12 12-6 1 1-6L16 3Zm-9 9 5 5M14 5l5 5',
  history: 'M3 11a9 9 0 1 1 2 7M3 4v7h7m2-4v6l4 2',
  spark: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',
  practice: 'M8 4H5v17h14V4h-3M8 2h8v4H8zM8 11l2 2 5-5M8 17h8',
  lock: 'M7 10V7a5 5 0 0 1 10 0v3M5 10h14v11H5zM12 14v3',
}
</script>

<template>
  <svg class="study-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name] || paths.spark" /></svg>
</template>
