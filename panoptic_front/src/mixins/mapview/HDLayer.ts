import * as THREE from 'three'
import { HDImageMaterial } from './HDImageMaterial'
import { PointData, ZoomParams } from '@/data/models'

const sharedPlaneGeo = new THREE.PlaneGeometry(1, 1)
const textureLoader = new THREE.TextureLoader()
const HD_Z_OFFSET = 1.5

const SCALE_NORMAL = 1.0
const SCALE_HOVER = 2.0
const LERP_FACTOR = 0.2
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
    private currentHoveredId: number | null = null;
    private colorHelper = new THREE.Color();

    constructor(scene: THREE.Scene, baseImgUrl: string) {
        this.scene = scene
        this.baseImgUrl = baseImgUrl
        this.group = new THREE.Group()
        this.scene.add(this.group)
    }

    // --- New Update Functions ---

    public updatePositions() {
        this.animationMap.forEach((state) => {
            const p = state.point;
            state.mesh.position.set(p.x, p.y, HD_Z_OFFSET);
            // FIX: Apply UNIFORM scaling only. 
            // The shader handles the aspect ratio using uRatio.
            state.mesh.scale.set(
                state.currentScale,
                state.currentScale,
                1.0
            );
        });
    }

    public updateTints() {
        this.animationMap.forEach((state) => {
            const mat = state.mesh.material as THREE.MeshBasicMaterial;
            mat.color.set(state.point.tint || '#FFFFFF');
        });
    }

    public updateBorderColors() {
        this.animationMap.forEach((state) => {
            const mat = state.mesh.material as HDImageMaterial;
            // Access the underlying shader uniform if available
            if (mat.userData.shader) {
                this.colorHelper.set(state.point.borderColor || '#000000');
                mat.userData.shader.uniforms.uBorderColor.value.copy(this.colorHelper);
            }
        });
    }

    // --- Core Logic ---

    public setZoomReference(zoomUniform: { value: number }) {
        this.zoomRef = zoomUniform;
    }

    public show(points: PointData[]) {
        points.sort((p1, p2) => p2.order - p1.order)
        const activeIds = new Set(points.map(p => p.id!))

        this.animationMap.forEach((state, id) => {
            state.isInShowList = activeIds.has(id);
        });

        this.cleanupUnusedImages();

        points.forEach(p => {
            if (this.animationMap.has(p.id!)) {
                // Ensure we have the latest data reference
                this.animationMap.get(p.id!)!.point = p;
                this.updateImagePosition(p)
            } else {
                this.createImage(p)
            }
        })
        this.setZoomParams(this.zoomParams)
        this.updateTints()
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
        const resolution = this.zoomRef.value > 7 ? 'large' : 'medium'
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
        // Pass ratio to the shader (Critical for Option A)
        mat.setRatio(p.ratio);

        const mesh = new THREE.Mesh(sharedPlaneGeo, mat)
        mesh.position.set(p.x, p.y, HD_Z_OFFSET)
        mesh.renderOrder = 2000 + (p.order || 0)
        
        // FIX: Start with 1x1x1 scale. No pre-scaling by ratio.
        mesh.scale.set(1.0, 1.0, 1.0)

        this.group.add(mesh)
        const isActuallyHovered = this.currentHoveredId === p.id

        this.animationMap.set(p.id!, {
            mesh,
            point: p,
            currentScale: SCALE_NORMAL,
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
            state.mesh.renderOrder = 2000 + (state.point.order || 0)
        }
    }

    public updateAnimations() {
        let needsCleanup = false;
        this.animationMap.forEach(state => {
            const diff = state.targetScale - state.currentScale;
            if (Math.abs(diff) > 0.001) {
                state.currentScale += diff * LERP_FACTOR
                
                // FIX: Update only uniform scale. Do NOT multiply by ratio.
                state.mesh.scale.set(
                    state.currentScale,
                    state.currentScale,
                    1.0
                )
            } else if (!state.isInShowList && !state.isHovered) {
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