declare module 'simple-mind-map' {
  import type { CanvasNode } from './mindMap'

  export default class SimpleMindMap {
    static usePlugin(plugin: unknown): void
    constructor(options: Record<string, unknown> & { el: HTMLElement; data: CanvasNode })
    readonly view: { scale: number; translateXY(x: number, y: number): void; fit(): void; narrow(): void; enlarge(): void; setScale(scale: number, x?: number, y?: number): void }
    on(event: 'node_click' | 'node_tree_render_end', callback: (...args: any[]) => void): void
    setData(data: CanvasNode): void
    resize(): void
    destroy(): void
  }
}

declare module 'simple-mind-map/src/plugins/RainbowLines' {
  const plugin: unknown
  export default plugin
}
