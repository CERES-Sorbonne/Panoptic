import { ZoomParams } from '@/data/models';
import * as THREE from 'three';

export class InstancedImageMaterial extends THREE.MeshBasicMaterial {
    private _zoomRef: { value: number } = { value: 1.0 };
    private _zoomParams = new THREE.Vector3(1.0, 0.1, 0.8);
    private _borderWidth = { value: 0.00 };
    private _radius = { value: 0.05 };

    constructor(parameters: THREE.MeshBasicMaterialParameters, collNb: number, rowNb: number) {
        super(parameters);

        this.onBeforeCompile = (shader) => {
            shader.uniforms.uGridCols = { value: collNb };
            shader.uniforms.uGridRows = { value: rowNb };
            shader.uniforms.uBorderWidth = this._borderWidth;
            shader.uniforms.uRadius = this._radius;
            shader.uniforms.uZoom = this._zoomRef;
            shader.uniforms.uZoomParams = { value: this._zoomParams };

            shader.vertexShader = `
    attribute vec2 vOffset;
    attribute vec4 vUvTransform; 
    attribute vec3 vTint;
    attribute vec3 vBorderCol;
    attribute float vRatioAttr; // <--- ADDED THIS

    varying vec2 vMappedUv;
    varying vec2 vRawUv; 
    varying vec3 vInstanceTint;
    varying vec3 vInstanceBorder;
    varying float vRatio; 

    uniform float uGridCols;
    uniform float uGridRows;
    uniform float uZoom;
    uniform vec3 uZoomParams;

    ${shader.vertexShader}
`.replace(
    `#include <begin_vertex>`,
    `
    vec3 transformed = vec3( position );
    float h  = uZoomParams.x;
    float z1 = uZoomParams.y;
    float z2 = uZoomParams.z;

    // Use the attribute directly
    vRatio = vRatioAttr; 

    float zoomScale = h;
    if(uZoom >= z1 && uZoom < z2) {
        zoomScale = h * (z1 / uZoom);
    } else if(uZoom >= z2) {
        zoomScale = h * (z1 / z2);
    }

    // FIT LOGIC: Calculate scale to fit in 1.0 x 1.0 box
    vec2 sizeScale;
    if(vRatio > 1.0) {
        // Landscape: Width is 1.0, Height is 1/Ratio
        sizeScale = vec2(1.0, 1.0 / vRatio);
    } else {
        // Portrait: Height is 1.0, Width is Ratio
        sizeScale = vec2(vRatio, 1.0);
    }

    transformed.xy *= sizeScale * zoomScale;
    `
).replace(
    `#include <uv_vertex>`,
    `
    #include <uv_vertex>
    vRawUv = uv;
    
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
    varying float vRatio; // Received from vertex shader

    uniform float uBorderWidth;
    uniform float uRadius;

    float sdRoundedBox(vec2 p, vec2 b, float r) {
        vec2 q = abs(p) - b + r;
        return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
    }

    ${shader.fragmentShader}
`.replace(
    `#include <map_fragment>`,
    `
    // Use the same fit logic for SDF bounds
    vec2 dimensions;
    if(vRatio > 1.0) {
        dimensions = vec2(1.0, 1.0 / vRatio);
    } else {
        dimensions = vec2(vRatio, 1.0);
    }
    
    vec2 p = (vRawUv - 0.5) * dimensions;
    vec2 b = dimensions * 0.5;
    
    float d = sdRoundedBox(p, b, uRadius);
    
    float aa = 0.002; 
    float outsideMask = smoothstep(aa, 0.0, d);
    float borderMask = smoothstep(aa, 0.0, d + uBorderWidth);

    vec4 texelColor = texture2D( map, vMappedUv );
    texelColor.rgb *= vInstanceTint;

    vec3 finalRGB = mix(vInstanceBorder, texelColor.rgb, borderMask);
    diffuseColor = vec4(finalRGB, texelColor.a * outsideMask);
    `
);

            this.userData.shader = shader;
        };
    }

    public setRadius(radius: number) {
        this._radius.value = radius;
        if (this.userData.shader) {
            this.userData.shader.uniforms.uRadius.value = radius;
        }
    }

    public setBorderWidth(width: number) {
        this._borderWidth.value = width;
        if (this.userData.shader) {
            this.userData.shader.uniforms.uBorderWidth.value = width;
        }
    }

    public setZoomParams(params: ZoomParams) {
        this._zoomParams.set(params.h, params.z1, params.z2);
        if (this.userData.shader) {
            this.userData.shader.uniforms.uZoomParams.value = this._zoomParams;
        }
    }

    public setZoomReference(zoomUniform: { value: number }) {
        this._zoomRef = zoomUniform;
        if (this.userData.shader) {
            this.userData.shader.uniforms.uZoom = zoomUniform;
        }
    }
}