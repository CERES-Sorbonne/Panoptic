import { PointData } from '@/data/models';
import KDBush from 'kdbush';

export class SpatialIndex {
    private tree: KDBush | null = null;
    private idToPointMap: Map<number, PointData> = new Map();

    /**
     * Initializes the spatial index with a new set of points
     */
    public initTree(points: PointData[]): void {
        this.idToPointMap.clear();
        this.tree = new KDBush(points.length);

        for (const point of points) {
            // KDBush returns a numeric index/id for each point added
            const id = this.tree.add(point.x, point.y);
            this.idToPointMap.set(id, point);
            point.id = id;
        }

        this.tree.finish();
    }

    /**
     * Returns all points within a given rectangular bounds [minX, minY, maxX, maxY]
     */
    public getPointsInRect(rect: {minX: number, minY: number, maxX: number, maxY: number}): PointData[] {
        if (!this.tree) return [];

        const indices = this.tree.range(rect.minX, rect.minY, rect.maxX, rect.maxY);
        return indices.map(idx => this.idToPointMap.get(idx)!);
    }

    /**
     * Returns the single nearest point to a specific X, Y coordinate
     * within an optional search radius
     */
    public getNearestPoint(x: number, y: number, radius: number = Infinity): PointData | null {
        if (!this.tree) return null;

        const indices = this.tree.within(x, y, radius);
        if (indices.length === 0) return null;

        return this.idToPointMap.get(indices[0]) || null;
    }

    /**
     * Clears the index and internal maps
     */
    public clear(): void {
        this.tree = null;
        this.idToPointMap.clear();
    }
}