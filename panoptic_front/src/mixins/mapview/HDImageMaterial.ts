import { ZoomParams } from '@/data/models';
import * as THREE from 'three';

export class HDImageMaterial extends THREE.MeshBasicMaterial {
    private _zoomRef: { value: number } = { value: 1.0 };
    private _zoomParams = new THREE.Vector3(1.0, 0.1, 0.8);
    private _ratio = { value: 1.0 };
    private _borderColor = { value: new THREE.Color(0x000000) };
    private _borderWidth = { value: 0.00 };
    private _radius = { value: 0.05 };

    constructor(parameters: THREE.MeshBasicMaterialParameters) {
        super(parameters);

        this.onBeforeCompile = (shader) => {
            shader.uniforms.uZoom = this._zoomRef;
            shader.uniforms.uZoomParams = { value: this._zoomParams };
            shader.uniforms.uRatio = this._ratio;
            shader.uniforms.uBorderColor = this._borderColor;
            shader.uniforms.uBorderWidth = this._borderWidth;
            shader.uniforms.uRadius = this._radius;

            shader.vertexShader = `
                varying vec2 vRawUv;
                uniform float uZoom;
                uniform vec3 uZoomParams;
                uniform float uRatio;
                ${shader.vertexShader}
            `.replace(
                `#include <begin_vertex>`,
                `
                vec3 transformed = vec3( position );
                float h  = uZoomParams.x;
                float z1 = uZoomParams.y;
                float z2 = uZoomParams.z;

                float zoomScale = h;
                if(uZoom >= z1 && uZoom < z2) {
                    zoomScale = h * (z1 / uZoom);
                } else if(uZoom >= z2) {
                    zoomScale = h * (z1 / z2);
                }

                // Calculate vector scale to fit in 1.0 x 1.0 box while keeping aspect ratio
                vec2 sizeScale;
                if(uRatio > 1.0) {
                    // Landscape: Width fixed to 1.0, Height reduces
                    sizeScale = vec2(1.0, 1.0 / uRatio);
                } else {
                    // Portrait/Square: Height fixed to 1.0, Width reduces
                    sizeScale = vec2(uRatio, 1.0);
                }

                // Apply specific X and Y scaling
                transformed.xy *= sizeScale * zoomScale;
                `
            ).replace(
                `#include <uv_vertex>`,
                `#include <uv_vertex>
                 vRawUv = uv;`
            );

            shader.fragmentShader = `
                varying vec2 vRawUv;
                uniform float uBorderWidth;
                uniform float uRatio;
                uniform vec3 uBorderColor;
                uniform float uRadius;

                float sdRoundedBox(vec2 p, vec2 b, float r) {
                    vec2 q = abs(p) - b + r;
                    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
                }

                ${shader.fragmentShader}
            `.replace(
                `#include <map_fragment>`,
                `
                vec2 dimensions;
                if(uRatio > 1.0) {
                    dimensions = vec2(1.0, 1.0 / uRatio);
                } else {
                    dimensions = vec2(uRatio, 1.0);
                }
                
                vec2 p = (vRawUv - 0.5) * dimensions;
                vec2 b = dimensions * 0.5;
                
                float d = sdRoundedBox(p, b, uRadius);
                
                float edgeSoftness = 0.002;
                float outsideMask = smoothstep(edgeSoftness, 0.0, d);
                float borderMask = smoothstep(edgeSoftness, 0.0, d + uBorderWidth);

                vec4 texelColor = texture2D( map, vRawUv );
                texelColor.rgb *= diffuse;

                vec3 finalRGB = mix(uBorderColor, texelColor.rgb, borderMask);
                
                diffuseColor = vec4(finalRGB, texelColor.a * outsideMask);
                `
            );

            this.userData.shader = shader;
        };
    }

    public setZoomReference(zoomUniform: { value: number }) {
        this._zoomRef = zoomUniform;
    }

    public setZoomParams(params: ZoomParams) {
        this._zoomParams.set(params.h, params.z1, params.z2);
    }

    public setRatio(ratio: number) {
        this._ratio.value = ratio;
    }

    public setRadius(radius: number) {
        this._radius.value = radius;
    }

    public setBorder(width: number, color: string) {
        this._borderWidth.value = width
        this._borderColor.value = new THREE.Color(color)
    }
}