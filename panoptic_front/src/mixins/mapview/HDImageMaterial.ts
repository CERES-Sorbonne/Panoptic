import { ZoomParams } from '@/data/models';
import * as THREE from 'three';

export class HDImageMaterial extends THREE.MeshBasicMaterial {
    private _zoomRef: { value: number } = { value: 1.0 };
    private _zoomParams = new THREE.Vector3(1.0, 0.1, 0.8); // h, z1, z2
    private _ratio = { value: 1.0 };
    private _borderColor = { value: new THREE.Color(0x000000) };
    private _borderWidth = { value: 0.04 };

    constructor(parameters: THREE.MeshBasicMaterialParameters) {
        super(parameters);

        this.onBeforeCompile = (shader) => {
            shader.uniforms.uZoom = this._zoomRef;
            shader.uniforms.uZoomParams = { value: this._zoomParams };
            shader.uniforms.uRatio = this._ratio;
            shader.uniforms.uBorderColor = this._borderColor;
            shader.uniforms.uBorderWidth = this._borderWidth;

            shader.vertexShader = `
                varying vec2 vRawUv;
                uniform float uZoom;
                uniform vec3 uZoomParams; // x:h, y:z1, z:z2
                ${shader.vertexShader}
            `.replace(
                `#include <begin_vertex>`,
                `
                vec3 transformed = vec3( position );
                float h  = uZoomParams.x;
                float z1 = uZoomParams.y;
                float z2 = uZoomParams.z;

                if(uZoom < z1) {
                    transformed.xy *= h;
                } else if(uZoom < z2) {
                    transformed.xy *= h * (z1 / uZoom);
                } else {
                    transformed.xy *= h * (z1 / z2);
                }
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
                ${shader.fragmentShader}
            `.replace(
                `#include <map_fragment>`,
                `
                vec4 texelColor = texture2D( map, vRawUv );
                
                // --- ADAPTATION FOR TINT ---
                // MeshBasicMaterial uses the 'diffuse' uniform for the .color property
                texelColor.rgb *= diffuse; 
                
                float b = uBorderWidth;
                vec3 finalRGB = texelColor.rgb;

                if (b > 0.0005) {
                    float inset = 0.001;
                    vec2 stableUv = vRawUv * (1.0 - inset * 2.0) + inset;
                    float bx = b / uRatio;
                    float by = b;
                    bx = min(bx, 0.5);
                    by = min(by, 0.5);
                    float aa = 0.005; 
                    float borderMask = smoothstep(bx, bx + aa, stableUv.x) * smoothstep(by, by + aa, stableUv.y) * smoothstep(bx, bx + aa, 1.0 - stableUv.x) * smoothstep(by, by + aa, 1.0 - stableUv.y);
                    finalRGB = mix(uBorderColor, texelColor.rgb, borderMask);
                }
                diffuseColor = vec4(finalRGB, texelColor.a);
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
}