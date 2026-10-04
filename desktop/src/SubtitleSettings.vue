<script setup lang="ts">
import { ref } from 'vue'
import { defaultAppearance } from './subtitleAppearance'
import type { SubtitleAppearance } from './subtitleAppearance'
const model=defineModel<SubtitleAppearance>({required:true})
const open=ref(false)
function update(key:keyof SubtitleAppearance,event:Event){const input=event.target as HTMLInputElement;model.value={...model.value,[key]:input.type==='checkbox'?input.checked:input.type==='range'?Number(input.value):input.value}}
</script>
<template>
  <div class="subtitle-settings">
    <button class="subtitle-toggle" type="button" :aria-expanded="open" aria-controls="subtitle-appearance-panel" @click="open=!open">字幕设置</button>
    <section v-if="open" id="subtitle-appearance-panel" class="subtitle-settings-panel" aria-label="字幕位置与样式设置" @keydown.esc="open=false">
      <div class="subtitle-settings-heading"><strong>字幕外观</strong><button type="button" aria-label="关闭字幕设置" @click="open=false">×</button></div>
      <label>位置 <span>{{ model.vertical }}%</span><input aria-label="字幕垂直位置" type="range" min="5" max="90" :value="model.vertical" @input="update('vertical',$event)" /></label>
      <div class="subtitle-position-presets"><button v-for="preset in [{name:'顶部',value:15},{name:'居中',value:50},{name:'底部',value:80}]" :key="preset.value" type="button" @click="model={...model,vertical:preset.value}">{{ preset.name }}</button></div>
      <label>字号 <span>{{ model.fontSize }} px</span><input aria-label="字幕字号" type="range" min="16" max="48" :value="model.fontSize" @input="update('fontSize',$event)" /></label>
      <label class="subtitle-color-row">文字颜色<input aria-label="字幕文字颜色" type="color" :value="model.textColor" @input="update('textColor',$event)" /></label>
      <label>文字不透明度 <span>{{ model.textOpacity }}%</span><input aria-label="字幕文字不透明度" type="range" min="0" max="100" :value="model.textOpacity" @input="update('textOpacity',$event)" /></label>
      <label class="subtitle-color-row">背景颜色<input aria-label="字幕背景颜色" type="color" :value="model.backgroundColor" @input="update('backgroundColor',$event)" /></label>
      <label>背景不透明度 <span>{{ model.backgroundOpacity }}%</span><input aria-label="字幕背景不透明度" type="range" min="0" max="100" :value="model.backgroundOpacity" @input="update('backgroundOpacity',$event)" /></label>
      <div class="subtitle-style-options"><label><input type="checkbox" :checked="model.bold" @change="update('bold',$event)" />加粗</label><label><input type="checkbox" :checked="model.outline" @change="update('outline',$event)" />文字阴影</label></div>
      <p>0% 为完全透明。调整仅影响网页字幕，不改变视频原有文字。</p>
      <button type="button" class="subtitle-reset" @click="model={...defaultAppearance}">恢复默认</button>
    </section>
  </div>
</template>
