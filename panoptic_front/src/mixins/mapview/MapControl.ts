import * as THREE from 'three';
import { LassoLayer } from './LassoLayer';


export class MapControls {
    private camera: THREE.OrthographicCamera;
    private domElement: HTMLElement;

    // Interaction State
    private mode: string = 'pan';
    private isDragging = false;
    private isLassoing = false;
    private prevPos = { x: 0, y: 0 };
    private mouse = new THREE.Vector2(); // NDC coordinates (-1 to +1)

    private lasso: LassoLayer;

    // Zoom config
    public minZoom = 0.01;
    public maxZoom = 20;
    public zoomSpeed = 0.001;

    // Callbacks to notify the renderer
    public onUpdate: () => void = () => { };

    constructor(camera: THREE.OrthographicCamera, domElement: HTMLElement, lassoLayer: LassoLayer) {
        this.camera = camera;
        this.domElement = domElement;
        this.lasso = lassoLayer;
        this.init();
    }

    private init() {
        this.domElement.addEventListener('wheel', this.handleWheel, { passive: false });
        this.domElement.addEventListener('mousedown', this.handleMouseDown);
        // Window listeners ensure interaction continues even if mouse leaves the container
        window.addEventListener('mousemove', this.handleMouseMove);
        window.addEventListener('mouseup', this.handleMouseUp);
    }

    /**
     * Updates internal mouse coordinates and handles panning or lasso drawing
     */
    private handleMouseMove = (e: MouseEvent) => {
        const rect = this.domElement.getBoundingClientRect();

        // 1. Update Normalized Device Coordinates (NDC) for Raycasting
        this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        // 2. Handle Lasso Drawing (takes priority)
        if (this.isLassoing) {
            const worldPos = this.getMouseWorldPos();
            const screenPos = { x: e.clientX, y: e.clientY };
            this.lasso.move(worldPos, screenPos);
            this.onUpdate();
            return;
        }

        // 3. Handle Panning (only in pan mode)
        if (this.isDragging && this.mode === 'pan') {
            const dx = e.clientX - this.prevPos.x;
            const dy = e.clientY - this.prevPos.y;

            const worldWidth = (this.camera.right - this.camera.left) / this.camera.zoom;
            const worldHeight = (this.camera.top - this.camera.bottom) / this.camera.zoom;

            // Map pixels to world units for 1:1 panning movement
            this.camera.position.x -= dx * (worldWidth / rect.width);
            this.camera.position.y += dy * (worldHeight / rect.height);

            this.prevPos = { x: e.clientX, y: e.clientY };
            this.onUpdate();
        }
    };

    /**
     * Handles zooming while keeping the mouse position anchored in world space
     */
    private handleWheel = (e: WheelEvent) => {
        e.preventDefault();

        // Calculate world coordinates under mouse before zoom
        const worldWidth = (this.camera.right - this.camera.left) / this.camera.zoom;
        const worldHeight = (this.camera.top - this.camera.bottom) / this.camera.zoom;
        const mouseWorldX = this.camera.position.x + (this.mouse.x * worldWidth) / 2;
        const mouseWorldY = this.camera.position.y + (this.mouse.y * worldHeight) / 2;

        // Perform Zoom logic
        const zoomAmount = e.deltaY * -this.zoomSpeed * this.camera.zoom;
        this.camera.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.camera.zoom + zoomAmount));
        this.camera.updateProjectionMatrix();

        // Calculate world coordinates under mouse after zoom
        const newWorldWidth = (this.camera.right - this.camera.left) / this.camera.zoom;
        const newWorldHeight = (this.camera.top - this.camera.bottom) / this.camera.zoom;
        const newMouseWorldX = this.camera.position.x + (this.mouse.x * newWorldWidth) / 2;
        const newMouseWorldY = this.camera.position.y + (this.mouse.y * newWorldHeight) / 2;

        // Offset camera to keep mouse over the same world coordinate (the "anchor" effect)
        this.camera.position.x += mouseWorldX - newMouseWorldX;
        this.camera.position.y += mouseWorldY - newMouseWorldY;

        this.onUpdate();
    };

    private handleMouseDown = (e: MouseEvent) => {
        // Lasso mode - only start lasso, never pan
        if (this.mode.startsWith('lasso')) {
            this.isLassoing = true;
            const worldPos = this.getMouseWorldPos();
            const screenPos = { x: e.clientX, y: e.clientY };
            this.lasso.start(worldPos, screenPos);
            this.domElement.style.cursor = 'crosshair';
            this.onUpdate();
        } 
        // Pan mode - only pan, never lasso
        else if (this.mode === 'pan') {
            this.isDragging = true;
            this.prevPos = { x: e.clientX, y: e.clientY };
            this.domElement.style.cursor = 'grabbing';
        }
    };

    private handleMouseUp = () => {
        if (this.isLassoing) {
            this.isLassoing = false;
            this.lasso.end();
            this.updateCursor();
            this.onUpdate();
        }
        
        if (this.isDragging) {
            this.isDragging = false;
            this.updateCursor();
        }
    };

    // --- Mode Management ---

    /**
     * Set the interaction mode (pan or lasso*)
     */
    public setMode(mode: string) {
        // Cancel any ongoing interactions when switching modes
        if (this.isLassoing) {
            this.lasso.clear();
            this.isLassoing = false;
        }
        this.isDragging = false;

        this.mode = mode;
        this.updateCursor();
        console.log("mode", mode);
    }

    /**
     * Get the current interaction mode
     */
    public getMode(): string {
        return this.mode;
    }

    /**
     * Update cursor based on current mode and state
     */
    private updateCursor() {
        if (this.isLassoing) {
            this.domElement.style.cursor = 'crosshair';
        } else if (this.isDragging) {
            this.domElement.style.cursor = 'grabbing';
        } else if (this.mode.startsWith('lasso')) {
            this.domElement.style.cursor = 'crosshair';
        } else if (this.mode === 'pan') {
            this.domElement.style.cursor = 'grab';
        } else {
            this.domElement.style.cursor = 'default';
        }
    }

    // --- Public Getters ---

    /**
     * Returns mouse position in Normalized Device Coordinates (-1 to 1)
     */
    public getMouseNDC(): THREE.Vector2 {
        return this.mouse;
    }

    /**
     * Returns the current mouse position converted to World Space coordinates
     */
    public getMouseWorldPos(): THREE.Vector3 {
        const worldPos = new THREE.Vector3();
        const worldWidth = (this.camera.right - this.camera.left) / this.camera.zoom;
        const worldHeight = (this.camera.top - this.camera.bottom) / this.camera.zoom;

        worldPos.x = this.camera.position.x + (this.mouse.x * worldWidth) / 2;
        worldPos.y = this.camera.position.y + (this.mouse.y * worldHeight) / 2;
        worldPos.z = 0;

        return worldPos;
    }

    /**
     * Cleanup event listeners
     */
    public dispose() {
        this.domElement.removeEventListener('wheel', this.handleWheel);
        this.domElement.removeEventListener('mousedown', this.handleMouseDown);
        window.removeEventListener('mousemove', this.handleMouseMove);
        window.removeEventListener('mouseup', this.handleMouseUp);
    }
}