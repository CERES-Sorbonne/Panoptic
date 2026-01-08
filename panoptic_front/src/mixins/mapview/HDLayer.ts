import * as THREE from 'three'
import { PointData } from './useMapLogic'
import { HDImageMaterial } from './HDImageMaterial'
import { ZoomParams } from '@/data/models'

const sharedPlaneGeo = new THREE.PlaneGeometry(1, 1)
const textureLoader = new THREE.TextureLoader()
const HD_Z_OFFSET = 1.5

const SCALE_NORMAL = 1.0
const SCALE_HOVER = 1.3
const LERP_FACTOR = 0.15
const ANIMATION_THRESHOLD = 0.005;

interface AnimationState {
    mesh: THREE.Mesh
    point: PointData
    currentScale: number
    targetScale: number
    isHovered: boolean;
    isInShowList: boolean;
}

export class HDLayer {
    public group: THREE.Group
    private scene: THREE.Scene
    private baseImgUrl: string
    private animationMap: Map<number, AnimationState> = new Map()
    private textureCache: Map<string, THREE.Texture> = new Map()
    private zoomRef: { value: number } = { value: 1.0 }
    private zoomParams: ZoomParams = { h: 1.0, z1: 0.2, z2: 0.8 }
    private currentHoveredId: number | null;

    constructor(scene: THREE.Scene, baseImgUrl: string) {
        this.scene = scene
        this.baseImgUrl = baseImgUrl
        this.group = new THREE.Group()
        this.scene.add(this.group)
    }

    public setZoomReference(zoomUniform: { value: number }) {
        this.zoomRef = zoomUniform;
    }

    public show(points: PointData[]) {
        points.sort((p1, p2) => p2.order - p1.order)
        const activeIds = new Set(points.map(p => p.id!))

        // Mark current items as in or out of the show list
        this.animationMap.forEach((state, id) => {
            state.isInShowList = activeIds.has(id);
        });

        // Cleanup: Only remove if not in show list, not hovered, and not animating
        this.cleanupUnusedImages();

        points.forEach(p => {
            if (this.animationMap.has(p.id!)) {
                this.updateImagePosition(p)
            } else {
                this.createImage(p)
            }
        })
        this.setZoomParams(this.zoomParams)
    }

    private cleanupUnusedImages() {
        this.animationMap.forEach((state, id) => {
            const isAnimating = Math.abs(state.targetScale - state.currentScale) > ANIMATION_THRESHOLD;
            if (!state.isInShowList && !state.isHovered && !isAnimating) {
                this.removeImage(id);
            }
        });
    }

    private getResolutionUrl(sha1: string): string {
        const resolution = this.zoomRef.value < 0.5 ? 'large' : 'medium'
        return `${this.baseImgUrl}${resolution}/${sha1}`
    }

    private createImage(p: PointData) {
        const url = this.getResolutionUrl(p.sha1)
        if (this.textureCache.has(url)) {
            this.setupMesh(p, this.textureCache.get(url)!)
        } else {
            textureLoader.load(url, (tex) => {
                tex.colorSpace = THREE.SRGBColorSpace
                this.textureCache.set(url, tex)
                if (this.group.parent) this.setupMesh(p, tex)
            })
        }
    }

    private setupMesh(p: PointData, tex: THREE.Texture) {
        if (this.animationMap.has(p.id!)) return;

        const mat = new HDImageMaterial({
            map: tex,
            transparent: true,
            side: THREE.DoubleSide
        });

        mat.setZoomReference(this.zoomRef);
        mat.setRatio(p.ratio);

        const mesh = new THREE.Mesh(sharedPlaneGeo, mat)
        mesh.position.set(p.x, p.y, HD_Z_OFFSET)
        mesh.renderOrder = 2000 + p.order
        mesh.scale.set(p.ratio, 1.0, 1.0)

        this.group.add(mesh)
        const isActuallyHovered = this.currentHoveredId === p.id

        this.animationMap.set(p.id!, {
            mesh,
            point: p,
            currentScale: SCALE_NORMAL,
            // Check if this image was loaded specifically because of a hover
            targetScale: isActuallyHovered ? SCALE_HOVER : SCALE_NORMAL,
            isHovered: isActuallyHovered,
            isInShowList: false 
        });

        if (isActuallyHovered) {
            mesh.renderOrder = Number.MAX_SAFE_INTEGER;
        }
    }

    private updateImagePosition(p: PointData) {
        const state = this.animationMap.get(p.id!)
        if (state) state.mesh.position.set(p.x, p.y, HD_Z_OFFSET)
    }

    public hover(point: PointData) {
        this.currentHoveredId = point.id;
        let state = this.animationMap.get(point.id!)
        if (!state) {
            this.createImage(point)
            // Note: Since createImage is async, state will be updated in next cycles
            return 
        }
        state.isHovered = true;
        state.targetScale = SCALE_HOVER
        state.mesh.renderOrder = Number.MAX_SAFE_INTEGER
    }

    public unhover(id: number) {
        const state = this.animationMap.get(id)
        if (state) {
            state.isHovered = false;
            state.targetScale = SCALE_NORMAL
            state.mesh.renderOrder = 2000 + state.point.order
        }
    }

    public updateAnimations() {
        let needsCleanup = false;
        this.animationMap.forEach(state => {
            const diff = state.targetScale - state.currentScale;
            if (Math.abs(diff) > 0.001) {
                state.currentScale += diff * LERP_FACTOR
                state.mesh.scale.set(
                    state.point.ratio * state.currentScale,
                    state.currentScale,
                    1.0
                )
            } else if (!state.isInShowList && !state.isHovered) {
                // If animation stopped and it's not in the show list or hovered, mark for cleanup
                needsCleanup = true;
            }
        })

        if (needsCleanup) {
            this.cleanupUnusedImages();
        }
    }

    private removeImage(id: number) {
        const state = this.animationMap.get(id)
        if (state) {
            this.group.remove(state.mesh)
            if (Array.isArray(state.mesh.material)) {
                state.mesh.material.forEach(m => m.dispose())
            } else {
                state.mesh.material.dispose()
            }
            this.animationMap.delete(id)
        }
    }

    public setZoomParams(params: ZoomParams) {
        this.zoomParams = params
        this.animationMap.forEach(state => {
            const mat = state.mesh.material as HDImageMaterial;
            mat.setZoomParams(params);
        });
    }

    public dispose() {
        const ids = Array.from(this.animationMap.keys());
        ids.forEach(id => this.removeImage(id));
        this.group.clear();
        this.textureCache.forEach(t => t.dispose())
        this.textureCache.clear()
        this.scene.remove(this.group)
    }
}