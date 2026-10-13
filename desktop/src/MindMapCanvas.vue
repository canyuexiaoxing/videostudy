<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import SimpleMindMap from 'simple-mind-map'
import RainbowLines from 'simple-mind-map/src/plugins/RainbowLines'
import 'simple-mind-map/dist/simpleMindMap.esm.css'
import { toCanvasNode } from './mindMap'
import type { MindMapNode } from './mindMap'

const props = defineProps<{ root: MindMapNode }>()
const emit = defineEmits<{ select: [node: MindMapNode] }>()
const container = ref<HTMLElement | null>(null)
let canvas: SimpleMindMap | null = null
let resizeObserver: ResizeObserver | null = null
let nodes = new Map<string, MindMapNode>()
let expandedDepth = Infinity
let fitAfterRender = false
let readingZoomAfterRender = false

function indexNodes(root: MindMapNode) {
  nodes = new Map()
  const pending = [root]
  while (pending.length) {
    const node = pending.pop()!
    nodes.set(node.id, node)
    pending.push(...node.children)
  }
}

function fit() {
  if (!canvas || !container.value?.clientWidth || !container.value.clientHeight) return
  canvas.resize()
  // Use viewport coordinates for both nodes and container. Library rbox includes
  // document scrolling, while its cached container rect uses viewport coordinates.
  const bounds = () => {
    const rects = Array.from(container.value!.querySelectorAll('.smm-node'))
      .map(node => node.getBoundingClientRect()).filter(r => r.width > 0 && r.height > 0)
    if (!rects.length) return null
    return { left: Math.min(...rects.map(r => r.left)), right: Math.max(...rects.map(r => r.right)),
      top: Math.min(...rects.map(r => r.top)), bottom: Math.max(...rects.map(r => r.bottom)) }
  }
  const before = bounds(), box = container.value.getBoundingClientRect()
  if (!before) return
  const scale = canvas.view.scale * Math.min((box.width - 48) / (before.right - before.left),
    (box.height - 48) / (before.bottom - before.top))
  if (!Number.isFinite(scale) || scale <= 0) return
  canvas.view.setScale(Math.min(1, scale))
  const after = bounds()
  if (after) canvas.view.translateXY(box.left + box.width / 2 - (after.left + after.right) / 2,
    box.top + box.height / 2 - (after.top + after.bottom) / 2)
}
function zoomIn() { canvas?.view.enlarge() }
function zoomOut() { canvas?.view.narrow() }
function applyReadingZoom() {
  if (container.value && canvas && container.value.clientWidth >= 500 && container.value.clientWidth < 760 && canvas.view.scale < 0.82) {
    canvas.view.setScale(0.82, container.value.clientWidth / 2, container.value.clientHeight / 2)
  }
}
function setExpandedDepth(depth: number) {
  expandedDepth = depth
  fitAfterRender = true
  readingZoomAfterRender = depth === 1
  canvas?.setData(toCanvasNode(props.root, depth))
}

function initialize() {
  // A hidden workbench tab has no drawable size. Initialize when it becomes visible.
  if (canvas || !container.value?.clientWidth || !container.value.clientHeight) return
  indexNodes(props.root)
  expandedDepth = nodes.size > 80 && container.value.clientWidth < 760 ? 1 : nodes.size > 80 ? 2 : Infinity
  SimpleMindMap.usePlugin(RainbowLines)
  fitAfterRender = true
  canvas = new SimpleMindMap({
    el: container.value,
    data: toCanvasNode(props.root, expandedDepth),
    layout: 'logicalStructure',
    readonly: true,
    fit: false,
    mousewheelAction: 'zoom',
    rainbowLinesConfig: {
      open: true,
      colorsList: ['#5c83e8', '#a77ae4', '#ea9a61', '#d777ae', '#56afce', '#d2a94e'],
    },
    themeConfig: {
      backgroundColor: '#ffffff',
      lineStyle: 'curve',
      lineWidth: 2,
      lineColor: '#7286b2',
      nodeUseLineStyle: true,
      paddingX: 8,
      paddingY: 5,
      root: { fillColor: '#5146aa', color: '#ffffff', fontSize: 17, borderRadius: 12,
        paddingX: 18, paddingY: 10 },
      second: { fillColor: 'transparent', color: '#29334f', fontSize: 15, fontWeight: 'bold',
        borderWidth: 0, marginX: 72, marginY: 22 },
      node: { fillColor: 'transparent', color: '#39435d', fontSize: 14,
        borderWidth: 0, marginX: 40, marginY: 6 },
    },
  })
  canvas.on('node_click', (item: { nodeData?: { data?: { _sourceId?: string } } }) => {
    const sourceId = item.nodeData?.data?._sourceId
    const original = sourceId ? nodes.get(sourceId) : null
    if (original) emit('select', original)
  })
  canvas.on('node_tree_render_end', () => {
    if (fitAfterRender) {
      fitAfterRender = false
      fit()
      if (readingZoomAfterRender) {
        readingZoomAfterRender = false
        applyReadingZoom()
      }
    }
  })
  window.setTimeout(fit, 200)
}
onMounted(() => {
  if (!container.value) return
  resizeObserver = new ResizeObserver(() => {
    if (!container.value?.clientWidth || !container.value.clientHeight) return
    if (canvas) canvas.resize()
    else initialize()
  })
  resizeObserver.observe(container.value)
  initialize()
})

watch(() => props.root, root => {
  indexNodes(root)
  expandedDepth = nodes.size > 80 && (container.value?.clientWidth ?? 0) < 760 ? 1 : nodes.size > 80 ? 2 : Infinity
  fitAfterRender = true
  readingZoomAfterRender = expandedDepth === 1
  canvas?.setData(toCanvasNode(root, expandedDepth))
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  canvas?.destroy()
})
</script>

<template>
  <div class="map-canvas-shell">
    <div class="map-toolbar" aria-label="导图视图操作">
      <span>拖动画布查看分支 · 滚轮缩放</span>
      <div>
        <button type="button" @click="setExpandedDepth(1)">聚焦主题</button>
        <button type="button" @click="setExpandedDepth(Infinity)">展开全部</button>
        <button type="button" aria-label="缩小导图" @click="zoomOut">−</button>
        <button type="button" aria-label="放大导图" @click="zoomIn">＋</button>
        <button type="button" @click="fit">适应画布</button>
      </div>
    </div>
    <div ref="container" class="mind-map-canvas" role="group" aria-label="可缩放的课程思维导图" />
  </div>
</template>
