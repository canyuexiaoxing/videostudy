<script setup lang="ts">
import {computed} from 'vue'
import {mathParts} from './mathText'
import 'katex/dist/katex.min.css'
const props=defineProps<{text:string}>()
const parts=computed(()=>mathParts(props.text))
</script>
<template><span class="math-text"><template v-for="(part,i) in parts" :key="i"><span v-if="part.html" class="math-formula" :class="{display:part.display}" v-html="part.html"></span><span v-else :class="{'math-error':part.error}" :title="part.error?'公式格式暂无法显示，已保留原文':undefined">{{ part.text }}</span></template></span></template>
<style scoped>
.math-text{white-space:pre-wrap;overflow-wrap:anywhere;min-width:0}.math-formula{display:inline-block;max-width:100%;overflow-x:auto;overflow-y:hidden;vertical-align:middle;white-space:normal;padding:4px 7px;box-sizing:border-box}.math-formula.display{display:block;margin:7px 0;padding:8px 2px}.math-formula :deep(.katex-display){margin:0;text-align:left}.math-error{color:inherit;border-bottom:1px dotted #a4adc4}
</style>
