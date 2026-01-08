import { ZoomParams } from '@/data/models';
import * as THREE from 'three';

export class InstancedImageMaterial extends THREE.MeshBasicMaterial {
    // 1. Internal state stored in a way accessible to onBeforeCompile
    private _zoomRef: { value: number } = { value: 1.0 };
    private _zoomParams = new THREE.Vector3(1.0, 0.1, 1.3); // Default h, z1, z2
    private _borderWidth = { value: 0.05 };

    constructor(parameters: THREE.MeshBasicMaterialParameters, collNb: number, rowNb: number) {
        super(parameters);

        this.onBeforeCompile = (shader) => {
            // 2. Define and Link Uniforms
            shader.uniforms.uGridCols = { value: collNb };
            shader.uniforms.uGridRows = { value: rowNb };
            shader.uniforms.uBorderWidth = this._borderWidth;
            shader.uniforms.uZoom = this._zoomRef;
            shader.uniforms.uZoomParams = { value: this._zoomParams };

            shader.vertexShader = `
                attribute vec2 vOffset;
                attribute vec4 vUvTransform; 
                attribute vec3 vTint;
                attribute vec3 vBorderCol;
                
                varying vec2 vMappedUv;
                varying vec2 vRawUv; 
                varying vec3 vInstanceTint;
                varying vec3 vInstanceBorder;
                varying float vRatio; 

                uniform float uGridCols;
                uniform float uGridRows;
                uniform float uZoom;
                uniform vec3 uZoomParams; // x: h, y: z1, z: z2

                ${shader.vertexShader}
            `.replace(
                `#include <begin_vertex>`,
                `
                vec3 transformed = vec3( position );
                
                // Extract params from Vector3
                float h  = uZoomParams.x;
                float z1 = uZoomParams.y;
                float z2 = uZoomParams.z;

                // Scale vertices based on zoom thresholds to maintain visual consistency
                if(uZoom < z1) {
                    transformed.xy *= h;
                }
                else if(uZoom < z2) {
                    transformed.xy *= h * (z1 / uZoom);
                } 
                else {
                    transformed.xy *= h * (z1 / z2);
                }
                `
            ).replace(
                `#include <uv_vertex>`,
                `
                #include <uv_vertex>
                vRawUv = uv;
                
                // Extract physical aspect ratio from the instance matrix
                vRatio = length(vec3(instanceMatrix[0][0], instanceMatrix[0][1], instanceMatrix[0][2]));

                float margin = 0.0005; 
                vec2 safeUv = mix(vec2(margin), vec2(1.0 - margin), uv);
                vec2 correctedUv = safeUv * vUvTransform.xy + vUvTransform.zw;
                vMappedUv = (correctedUv / vec2(uGridCols, uGridRows)) + vOffset;
                
                vInstanceTint = vTint;
                vInstanceBorder = vBorderCol;
                `
            );

            shader.fragmentShader = `
                varying vec2 vMappedUv;
                varying vec2 vRawUv;
                varying vec3 vInstanceTint;
                varying vec3 vInstanceBorder;
                varying float vRatio;

                uniform float uBorderWidth;

                ${shader.fragmentShader}
            `.replace(
                `#include <map_fragment>`,
                `
                vec4 texelColor = texture2D( map, vMappedUv );
                texelColor.rgb *= vInstanceTint;

                float b = uBorderWidth;
                vec3 finalRGB = texelColor.rgb;

                if (b > 0.0005) {
                    float inset = 0.001;
                    vec2 stableUv = vRawUv * (1.0 - inset * 2.0) + inset;
                    
                    // Adjust border thickness based on aspect ratio
                    float bx = b / vRatio;
                    float by = b;

                    bx = min(bx, 0.5);
                    by = min(by, 0.5);

                    float aa = 0.002; 
                    float borderMask = smoothstep(bx, bx + aa, stableUv.x) * smoothstep(by, by + aa, stableUv.y) * smoothstep(bx, bx + aa, 1.0 - stableUv.x) * smoothstep(by, by + aa, 1.0 - stableUv.y);
                    
                    finalRGB = mix(vInstanceBorder, texelColor.rgb, borderMask);
                }

                diffuseColor = vec4(finalRGB, texelColor.a);
                `
            );

            // Store a reference to the shader for manual updates if needed
            this.userData.shader = shader;
        };
    }

    /**
     * Updates sizing behavior.
     * h: base multiplier, z1: start threshold, z2: end threshold
     */
    public setZoomParams(params: ZoomParams) {
        this._zoomParams.set(params.h, params.z1, params.z2);
        const shader = this.userData.shader;
        console.log("set params", shader)
        if (shader) {
            shader.uniforms.uZoomParams.value = this._zoomParams;
        }
    }

    /**
     * Connects this material to the global zoom uniform.
     */
    public setZoomReference(zoomUniform: { value: number }) {
        this._zoomRef = zoomUniform;
        const shader = this.userData.shader;
        if (shader) {
            shader.uniforms.uZoom = zoomUniform;
        }
    }

    /**
     * Updates the global border width for all instances in this layer.
     */
    public setBorderWidth(width: number) {
        this._borderWidth.value = width;
        const shader = this.userData.shader;
        if (shader) {
            shader.uniforms.uBorderWidth.value = width;
        }
    }
}