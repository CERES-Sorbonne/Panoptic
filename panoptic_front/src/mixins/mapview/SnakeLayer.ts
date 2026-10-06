import * as THREE from 'three'
import { edgeArrow, type Cell, type Rect, type SnakeBoard } from './GridSnake'

// Above every atlas tier, below the HD hover preview (1.5).
const Z = 1.3
// Every material here is `transparent`: three draws all opaque objects before transparent ones,
// and the atlas layers are transparent, so an opaque snake would be painted over by the
// thumbnails whatever its z or renderOrder.
const BODY_COLOR = new THREE.Color('#2fb344')
const HEAD_COLOR = new THREE.Color('#1a7a2c')
const FOOD_COLOR = '#ff2a2a'
const BOARD_COLOR = '#ff2a2a'
const ARROW_PX = 30

export interface SnakeView {
    board: SnakeBoard
    body: Cell[]
    food: Cell | null
}

// Draws the grid snake easter egg: the snake, a pulsing red highlight over the image to eat, a red
// arrow on the screen edge towards it while it is off screen, and the board's walls.
export class SnakeLayer {
    private scene: THREE.Scene
    private group = new THREE.Group()
    private plane = new THREE.PlaneGeometry(1, 1)
    private body: THREE.InstancedMesh | null = null
    private bodyMaterial = new THREE.MeshBasicMaterial({ transparent: true, depthWrite: false })
    private foodMaterial = new THREE.MeshBasicMaterial({ color: FOOD_COLOR, transparent: true, opacity: 0.5, depthWrite: false })
    private food: THREE.Mesh
    private foodFrame: THREE.LineSegments
    private boardFrame: THREE.LineLoop
    private arrow: THREE.Mesh
    private foodWorld: { x: number, y: number } | null = null
    // Screen strips (CSS px) covered by floating UI, kept clear of the arrow.
    private insets = { top: 0, right: 0, bottom: 0, left: 0 }
    private matrix = new THREE.Matrix4()

    constructor(scene: THREE.Scene) {
        this.scene = scene
        this.food = new THREE.Mesh(this.plane, this.foodMaterial)
        this.foodFrame = new THREE.LineSegments(new THREE.EdgesGeometry(this.plane), new THREE.LineBasicMaterial({ color: FOOD_COLOR, transparent: true, depthWrite: false }))
        this.food.add(this.foodFrame)
        const loop = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(-0.5, -0.5, 0), new THREE.Vector3(0.5, -0.5, 0),
            new THREE.Vector3(0.5, 0.5, 0), new THREE.Vector3(-0.5, 0.5, 0),
        ])
        this.boardFrame = new THREE.LineLoop(loop, new THREE.LineBasicMaterial({ color: BOARD_COLOR, transparent: true, depthWrite: false }))
        // Tip at the origin, pointing along +x.
        const shape = new THREE.Shape([new THREE.Vector2(0, 0), new THREE.Vector2(-1, 0.55), new THREE.Vector2(-0.75, 0), new THREE.Vector2(-1, -0.55)])
        this.arrow = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshBasicMaterial({ color: FOOD_COLOR, transparent: true, depthTest: false, depthWrite: false }))
        this.arrow.visible = false
        this.group.add(this.food, this.boardFrame, this.arrow)
        for (const o of [this.food, this.foodFrame, this.boardFrame]) o.renderOrder = Number.MAX_SAFE_INTEGER - 1
        this.arrow.renderOrder = Number.MAX_SAFE_INTEGER
        this.group.visible = false
        this.scene.add(this.group)
    }

    public render(view: SnakeView, cellToWorld: (c: number, r: number) => [number, number], cellSize: number) {
        this.group.visible = true
        // Grown on demand: the board can be the whole grid, far more cells than the snake needs.
        let capacity = 64
        while (capacity < view.body.length) capacity *= 2
        if (!this.body || this.body.instanceMatrix.count < capacity) {
            if (this.body) {
                this.group.remove(this.body)
                this.body.dispose()
            }
            this.body = new THREE.InstancedMesh(this.plane, this.bodyMaterial, capacity)
            this.body.frustumCulled = false
            this.body.renderOrder = Number.MAX_SAFE_INTEGER - 1
            this.group.add(this.body)
        }

        const segment = cellSize * 0.86
        view.body.forEach((p, i) => {
            const [x, y] = cellToWorld(p.c, p.r)
            this.matrix.makeScale(segment, segment, 1)
            this.matrix.setPosition(x, y, Z)
            this.body!.setMatrixAt(i, this.matrix)
            this.body!.setColorAt(i, i === 0 ? HEAD_COLOR : BODY_COLOR)
        })
        this.body.count = view.body.length
        this.body.instanceMatrix.needsUpdate = true
        if (this.body.instanceColor) this.body.instanceColor.needsUpdate = true

        this.food.visible = !!view.food
        this.foodWorld = null
        if (view.food) {
            const [x, y] = cellToWorld(view.food.c, view.food.r)
            this.food.position.set(x, y, Z)
            this.food.scale.set(cellSize, cellSize, 1)
            this.foodWorld = { x, y }
        }

        const b = view.board
        const [x0, y0] = cellToWorld(b.c0, b.r0)
        const [x1, y1] = cellToWorld(b.c0 + b.cols - 1, b.r0 + b.rows - 1)
        this.boardFrame.position.set((x0 + x1) / 2, (y0 + y1) / 2, Z)
        this.boardFrame.scale.set(x1 - x0 + cellSize, y1 - y0 + cellSize, 1)
    }

    public setInsets(insets: { top: number, right: number, bottom: number, left: number }) {
        this.insets = insets
    }

    // `view`: the camera's world rect; `worldPerPixel`: world units per CSS pixel.
    public tick(time: number, view: Rect, worldPerPixel: number) {
        if (!this.group.visible) return
        const pulse = 0.5 + 0.5 * Math.sin(time / 120)
        this.foodMaterial.opacity = 0.35 + 0.3 * pulse

        const size = ARROW_PX * worldPerPixel
        const margin = size * 0.4
        const inner = {
            minX: view.minX + this.insets.left * worldPerPixel + margin,
            maxX: view.maxX - this.insets.right * worldPerPixel - margin,
            minY: view.minY + this.insets.bottom * worldPerPixel + margin,
            maxY: view.maxY - this.insets.top * worldPerPixel - margin,
        }
        const arrow = this.foodWorld && inner.minX < inner.maxX && inner.minY < inner.maxY ? edgeArrow(inner, this.foodWorld) : null
        this.arrow.visible = !!arrow
        if (arrow) {
            this.arrow.position.set(arrow.x, arrow.y, Z + 0.1)
            this.arrow.rotation.z = arrow.angle
            this.arrow.scale.setScalar(size * (0.9 + 0.2 * pulse))
        }
    }

    public hide() {
        this.group.visible = false
    }

    public dispose() {
        this.scene.remove(this.group)
        this.body?.dispose()
        this.plane.dispose()
        this.bodyMaterial.dispose()
        this.foodMaterial.dispose()
        this.foodFrame.geometry.dispose()
        this.boardFrame.geometry.dispose()
        this.arrow.geometry.dispose()
    }
}
