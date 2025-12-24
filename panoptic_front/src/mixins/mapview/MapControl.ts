import * as THREE from 'three';

export class MapControls {
    private camera: THREE.OrthographicCamera;
    private domElement: HTMLElement;
    private isDragging = false;
    private prevPos = { x: 0, y: 0 };
    
    // Zoom config
    public minZoom = 0.01;
    public maxZoom = 20;
    public zoomSpeed = 0.001;

    // Callbacks to notify the renderer
    public onUpdate: () => void = () => {};

    constructor(camera: THREE.OrthographicCamera, domElement: HTMLElement) {
        this.camera = camera;
        this.domElement = domElement;
        this.init();
    }

    private init() {
        this.domElement.addEventListener('wheel', this.handleWheel, { passive: false });
        this.domElement.addEventListener('mousedown', this.handleMouseDown);
        window.addEventListener('mousemove', this.handleMouseMove);
        window.addEventListener('mouseup', this.handleMouseUp);
    }

    private handleWheel = (e: WheelEvent) => {
        e.preventDefault();
        
        const rect = this.domElement.getBoundingClientRect();
        const mouseX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        const mouseY = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        // Calculate world coordinates under mouse before zoom
        const worldWidth = (this.camera.right - this.camera.left) / this.camera.zoom;
        const worldHeight = (this.camera.top - this.camera.bottom) / this.camera.zoom;
        const mouseWorldX = this.camera.position.x + (mouseX * worldWidth) / 2;
        const mouseWorldY = this.camera.position.y + (mouseY * worldHeight) / 2;

        // Perform Zoom
        const zoomAmount = e.deltaY * -this.zoomSpeed * this.camera.zoom;
        this.camera.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.camera.zoom + zoomAmount));
        this.camera.updateProjectionMatrix();

        // Calculate world coordinates under mouse after zoom
        const newWorldWidth = (this.camera.right - this.camera.left) / this.camera.zoom;
        const newWorldHeight = (this.camera.top - this.camera.bottom) / this.camera.zoom;
        const newMouseWorldX = this.camera.position.x + (mouseX * newWorldWidth) / 2;
        const newMouseWorldY = this.camera.position.y + (mouseY * newWorldHeight) / 2;

        // Offset camera to keep mouse over the same world coordinate
        this.camera.position.x += mouseWorldX - newMouseWorldX;
        this.camera.position.y += mouseWorldY - newMouseWorldY;

        this.onUpdate();
    };

    private handleMouseDown = (e: MouseEvent) => {
        // Assume 'pan' mode check is done outside or passed in
        this.isDragging = true;
        this.prevPos = { x: e.clientX, y: e.clientY };
        this.domElement.style.cursor = 'grabbing';
    };

    private handleMouseMove = (e: MouseEvent) => {
        if (!this.isDragging) return;

        const dx = e.clientX - this.prevPos.x;
        const dy = e.clientY - this.prevPos.y;

        const rect = this.domElement.getBoundingClientRect();
        const worldWidth = (this.camera.right - this.camera.left) / this.camera.zoom;
        const worldHeight = (this.camera.top - this.camera.bottom) / this.camera.zoom;

        // Map pixels to world units for 1:1 panning
        this.camera.position.x -= dx * (worldWidth / rect.width);
        this.camera.position.y += dy * (worldHeight / rect.height);

        this.prevPos = { x: e.clientX, y: e.clientY };
        this.onUpdate();
    };

    private handleMouseUp = () => {
        this.isDragging = false;
        this.domElement.style.cursor = 'inherit';
    };

    public dispose() {
        this.domElement.removeEventListener('wheel', this.handleWheel);
        this.domElement.removeEventListener('mousedown', this.handleMouseDown);
        window.removeEventListener('mousemove', this.handleMouseMove);
        window.removeEventListener('mouseup', this.handleMouseUp);
    }
}