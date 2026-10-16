import { test } from "node:test";
import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
//#region src/data/models/property.ts
var PropertyType = /* @__PURE__ */ function(PropertyType) {
	PropertyType["multi_tags"] = "multi_tags";
	PropertyType["tag"] = "tag";
	PropertyType["string"] = "text";
	PropertyType["number"] = "number";
	PropertyType["date"] = "date";
	PropertyType["color"] = "color";
	PropertyType["url"] = "url";
	PropertyType["checkbox"] = "checkbox";
	PropertyType["path"] = "path";
	PropertyType["image_link"] = "image_link";
	PropertyType["_ahash"] = "ahash";
	PropertyType["_sha1"] = "sha1";
	PropertyType["_folders"] = "folder";
	PropertyType["_id"] = "id";
	PropertyType["_width"] = "width";
	PropertyType["_height"] = "height";
	return PropertyType;
}({});
//#endregion
//#region src/data/lib/columns.ts
function propertyKind(type) {
	if (type === PropertyType.number || type === PropertyType.date || type === PropertyType.color || type === PropertyType._width || type === PropertyType._height || type === PropertyType._id) return "numeric";
	if (type === PropertyType.checkbox) return "bool";
	if (type === PropertyType.multi_tags || type === PropertyType.tag) return "tag";
	return "string";
}
/** A value as a numeric column stores it: NaN for none, a date string as its timestamp. */
function numericCell(value, isDate) {
	if (isDate && typeof value === "string") return new Date(value).getTime();
	return value == null ? NaN : Number(value);
}
/** A value as a bool column stores it: 0, 1, 255 for none. */
function boolCell(value) {
	return value == null ? 255 : value ? 1 : 0;
}
function makeColumn(kind, size) {
	switch (kind) {
		case "numeric": {
			const data = new Float64Array(size);
			data.fill(NaN);
			return {
				kind,
				data
			};
		}
		case "bool": return {
			kind,
			data: new Uint8Array(size).fill(255)
		};
		case "string": return {
			kind,
			data: new Array(size).fill(null)
		};
		case "tag": return {
			kind,
			sparse: new Array(size).fill(null)
		};
	}
}
function buildCSR(sparse, count) {
	const offsets = new Int32Array(count + 1);
	let total = 0;
	for (let s = 0; s < count; s++) {
		total += sparse[s]?.length ?? 0;
		offsets[s + 1] = total;
	}
	const values = new Int32Array(total);
	let pos = 0;
	for (let s = 0; s < count; s++) {
		const tags = sparse[s];
		if (tags) for (const t of tags) values[pos++] = t;
	}
	return {
		offsets,
		values
	};
}
//#endregion
//#region src/viewer/data/staticData.ts
/**
* Reads an exported project (see ./format.ts): loads the data parts, decodes them, and turns
* columns into the column store's own layout.
*
* Every instance array is in the order of manifest.instances, which is also the slot order of
* the column store: the base stream hands the instances over in that order to an empty store.
* So a row of a part is a slot, and a decoded column can be adopted by the store as is.
*/
var parts = /* @__PURE__ */ new Map();
/**
* Load `data/<name>.js`. Each part is a classic script that stores its payload in
* window.__panopticData[name]: classic scripts load from any origin the site is served from,
* file:// included, and the payload is parsed once by the JS engine with no copy in between.
*/
function loadPart(name) {
	let pending = parts.get(name);
	if (!pending) {
		pending = new Promise((resolve, reject) => {
			const script = document.createElement("script");
			script.src = `data/${name}.js`;
			script.async = true;
			script.onload = () => {
				const store = window.__panopticData ?? {};
				const payload = store[name];
				delete store[name];
				script.remove();
				if (payload === void 0) reject(/* @__PURE__ */ new Error(`Viewer data part "${name}" is empty`));
				else resolve(payload);
			};
			script.onerror = () => {
				script.remove();
				reject(/* @__PURE__ */ new Error(`Viewer data part "${name}" could not be loaded`));
			};
			document.head.appendChild(script);
		});
		pending.catch(() => parts.delete(name));
		parts.set(name, pending);
	}
	return pending;
}
var manifestPromise = null;
function getManifest() {
	if (!manifestPromise) manifestPromise = loadPart("project").then((m) => {
		if (m.format !== 2) throw new Error(`This export uses data format ${m.format}, the viewer reads format 2`);
		buckets = [...m.images].sort((a, b) => bound(a) - bound(b));
		return m;
	});
	return manifestPromise;
}
function decodeBytes(b64) {
	const fromBase64 = Uint8Array.fromBase64;
	if (fromBase64) return fromBase64(b64);
	const bin = atob(b64);
	const bytes = new Uint8Array(bin.length);
	for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
	return bytes;
}
function decodeInt32(b64) {
	const bytes = decodeBytes(b64);
	return new Int32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength >> 2);
}
function decodeFloat64(b64) {
	const bytes = decodeBytes(b64);
	return new Float64Array(bytes.buffer, bytes.byteOffset, bytes.byteLength >> 3);
}
var base = null;
async function getInstanceBase() {
	if (base) return base;
	const m = await getManifest();
	const index = decodeInt32(m.instances.sha1Index);
	const table = m.instances.sha1s;
	const sha1s = new Array(index.length);
	for (let i = 0; i < index.length; i++) sha1s[i] = index[i] < 0 ? null : table[index[i]];
	base = {
		ids: decodeInt32(m.instances.ids),
		fileIds: decodeInt32(m.instances.fileIds),
		sha1s
	};
	return base;
}
var columns = /* @__PURE__ */ new Map();
/** The decoded column of a property, or null when the export holds no value for it. */
function getColumn(propertyId) {
	let pending = columns.get(propertyId);
	if (!pending) {
		pending = (async () => {
			if (!(await getManifest()).columns.includes(propertyId)) return null;
			return decodeColumn(await loadPart(`col/${propertyId}`));
		})();
		pending.catch(() => columns.delete(propertyId));
		columns.set(propertyId, pending);
	}
	return pending;
}
function decodeColumn(part) {
	switch (part.enc) {
		case "f64": return {
			enc: "f64",
			data: decodeFloat64(part.data)
		};
		case "bool": return {
			enc: "bool",
			data: decodeBytes(part.data)
		};
		case "dict": return {
			enc: "dict",
			values: part.values,
			index: decodeInt32(part.index)
		};
		case "tags": return {
			enc: "tags",
			offsets: decodeInt32(part.offsets),
			tags: decodeInt32(part.tags)
		};
	}
}
function rowCount(col) {
	switch (col.enc) {
		case "f64":
		case "bool": return col.data.length;
		case "dict": return col.index.length;
		case "tags": return col.offsets.length - 1;
	}
}
/**
* The value of one row as the backend sends it (/instances/values), undefined when there is
* none. Arrays are fresh copies: the caller may keep them.
*/
function rawValue(col, row) {
	switch (col.enc) {
		case "f64": {
			const v = col.data[row];
			return Number.isNaN(v) ? void 0 : v;
		}
		case "bool": {
			const v = col.data[row];
			return v === 255 ? void 0 : v === 1;
		}
		case "dict": {
			const i = col.index[row];
			if (i < 0) return void 0;
			const v = col.values[i];
			return Array.isArray(v) ? v.slice() : v;
		}
		case "tags": {
			const start = col.offsets[row], end = col.offsets[row + 1];
			return start === end ? void 0 : Array.from(col.tags.subarray(start, end));
		}
	}
}
/**
* The column store's layout of a column, one entry per slot. Converts each value with the cell
* conversions columnStore.writeSlot uses; the common pairs (numbers in a numeric column, tags
* in a tag column...) skip the per-cell conversion.
*/
function toColumnData(col, type) {
	const kind = propertyKind(type);
	const isDate = type === PropertyType.date;
	const n = rowCount(col);
	if (kind === "numeric" && col.enc === "f64") return {
		kind,
		data: col.data
	};
	if (kind === "bool" && col.enc === "bool") return {
		kind,
		data: col.data
	};
	if (kind === "tag" && col.enc === "tags") {
		const sparse = new Array(n);
		for (let r = 0; r < n; r++) {
			const start = col.offsets[r], end = col.offsets[r + 1];
			sparse[r] = start === end ? null : Array.from(col.tags.subarray(start, end));
		}
		return {
			kind,
			sparse,
			csr: {
				offsets: col.offsets,
				values: col.tags
			}
		};
	}
	if (col.enc === "dict") {
		const { values, index } = col;
		switch (kind) {
			case "numeric": {
				const converted = Float64Array.from(values, (v) => numericCell(v, isDate));
				const data = new Float64Array(n);
				for (let r = 0; r < n; r++) data[r] = index[r] < 0 ? NaN : converted[index[r]];
				return {
					kind,
					data
				};
			}
			case "bool": {
				const converted = Uint8Array.from(values, boolCell);
				const data = new Uint8Array(n);
				for (let r = 0; r < n; r++) data[r] = index[r] < 0 ? 255 : converted[index[r]];
				return {
					kind,
					data
				};
			}
			case "string": {
				const data = new Array(n);
				for (let r = 0; r < n; r++) data[r] = index[r] < 0 ? null : values[index[r]] ?? null;
				return {
					kind,
					data
				};
			}
		}
	}
	switch (kind) {
		case "numeric": {
			const data = new Float64Array(n);
			for (let r = 0; r < n; r++) data[r] = numericCell(rawValue(col, r), isDate);
			return {
				kind,
				data
			};
		}
		case "bool": {
			const data = new Uint8Array(n);
			for (let r = 0; r < n; r++) data[r] = boolCell(rawValue(col, r));
			return {
				kind,
				data
			};
		}
		case "string": {
			const data = new Array(n);
			for (let r = 0; r < n; r++) data[r] = rawValue(col, r) ?? null;
			return {
				kind,
				data
			};
		}
		case "tag": {
			const sparse = new Array(n);
			for (let r = 0; r < n; r++) {
				const v = rawValue(col, r);
				sparse[r] = Array.isArray(v) ? v : null;
			}
			return {
				kind,
				sparse
			};
		}
	}
}
/** A map's points in the backend's flat layout: [sha1, x, y, sha1, x, y, ...]. */
async function getMapData(mapId) {
	const m = await getManifest();
	const part = await loadPart(`map/${mapId}`);
	const index = decodeInt32(part.sha1Index);
	const xy = decodeFloat64(part.xy);
	const flat = new Array(index.length * 3);
	for (let i = 0; i < index.length; i++) {
		flat[3 * i] = m.instances.sha1s[index[i]];
		flat[3 * i + 1] = xy[2 * i];
		flat[3 * i + 2] = xy[2 * i + 1];
	}
	return flat;
}
/** The pyramid the map's images are drawn from, if it has points. */
function getMapPyramid(map) {
	const p = map.pyramid;
	if (!p) return void 0;
	return {
		order: p.order,
		levels: p.levels,
		tile: p.tile,
		url: `map/${map.id}/{cell}/{x}_{y}.jpg`,
		missing: Array.from(decodeInt32(p.missing))
	};
}
var buckets = [];
function bound(b) {
	return b.size ?? Infinity;
}
/**
* URL of the stored thumbnail of `sha1` that best fits `size`, picked like the backend's
* /image/by_size does: the smallest type at least `size` big, else the largest; the largest
* when no size is given.
*/
function imageUrl(sha1, size) {
	if (!sha1 || !buckets.length) return "";
	let pick = buckets[buckets.length - 1];
	if (size != null) pick = buckets.find((b) => bound(b) >= size) ?? pick;
	return `img/${pick.dir}/${sha1.slice(0, 2)}/${sha1}.${pick.ext}`;
}
//#endregion
//#region test/viewer/specs/static_data.ts
var files = {};
var g = globalThis;
g.window = g;
g.document = {
	createElement: () => ({ remove() {} }),
	head: { appendChild(script) {
		const name = script.src.replace(/^data\//, "").replace(/\.js$/, "");
		queueMicrotask(() => {
			if (!(name in files)) return script.onerror();
			(g.__panopticData ??= {})[name] = files[name];
			script.onload();
		});
	} }
};
var b64 = (a) => Buffer.from(a.buffer, a.byteOffset, a.byteLength).toString("base64");
var i32 = (xs) => b64(Int32Array.from(xs));
var f64 = (xs) => b64(Float64Array.from(xs));
var u8 = (xs) => b64(Uint8Array.from(xs));
files["project"] = {
	format: 2,
	exportId: "e1",
	exportedAt: "2026-10-08T00:00:00Z",
	panopticVersion: "test",
	project: {
		id: "p1",
		name: "test"
	},
	initState: {
		properties: [],
		tags: [],
		folders: [],
		file_sources: [],
		property_groups: [],
		sequence: 0
	},
	tabs: [],
	uiData: {},
	tagCounts: [],
	folderCounts: {},
	maps: [{
		id: 3,
		source: "test",
		name: "m",
		key: "sha1",
		count: 2,
		pyramid: {
			order: 1,
			levels: [64],
			tile: 1024,
			missing: i32([1])
		}
	}, {
		id: 4,
		source: "test",
		name: "empty",
		key: "sha1",
		count: 0
	}],
	instances: {
		count: 4,
		ids: i32([
			10,
			11,
			12,
			13
		]),
		fileIds: i32([
			1,
			2,
			0,
			3
		]),
		sha1s: [
			"aa11",
			"bb22",
			"cc33"
		],
		sha1Index: i32([
			0,
			1,
			1,
			-1
		])
	},
	columns: [
		1,
		2,
		3,
		4
	],
	images: [
		{
			dir: "2",
			size: 1024,
			ext: "jpg"
		},
		{
			dir: "1",
			size: 256,
			ext: "jpg"
		},
		{
			dir: "9",
			size: null,
			ext: "png"
		}
	]
};
files["col/1"] = {
	enc: "f64",
	data: f64([
		1.5,
		NaN,
		0,
		-2
	])
};
files["col/2"] = {
	enc: "bool",
	data: u8([
		1,
		0,
		255,
		1
	])
};
files["col/3"] = {
	enc: "dict",
	values: [
		"2024-09-01T00:00:00Z",
		"x",
		7,
		[3, 4]
	],
	index: i32([
		0,
		-1,
		1,
		3
	])
};
files["col/4"] = {
	enc: "tags",
	offsets: i32([
		0,
		2,
		2,
		3,
		3
	]),
	tags: i32([
		5,
		6,
		5
	])
};
files["map/3"] = {
	sha1Index: i32([2, 0]),
	xy: f64([
		.5,
		-1,
		3,
		4.25
	])
};
test("viewer data: instances in export order, one shared string per sha1", async () => {
	const base = await getInstanceBase();
	assert.deepEqual([...base.ids], [
		10,
		11,
		12,
		13
	]);
	assert.deepEqual([...base.fileIds], [
		1,
		2,
		0,
		3
	]);
	assert.deepEqual(base.sha1s, [
		"aa11",
		"bb22",
		"bb22",
		null
	]);
	assert.equal((await getManifest()).project.name, "test");
});
test("viewer data: raw values are what the backend sends, undefined for none", async () => {
	const values = async (id) => {
		const col = await getColumn(id);
		return [
			0,
			1,
			2,
			3
		].map((r) => rawValue(col, r));
	};
	assert.deepEqual(await values(1), [
		1.5,
		void 0,
		0,
		-2
	]);
	assert.deepEqual(await values(2), [
		true,
		false,
		void 0,
		true
	]);
	assert.deepEqual(await values(3), [
		"2024-09-01T00:00:00Z",
		void 0,
		"x",
		[3, 4]
	]);
	assert.deepEqual(await values(4), [
		[5, 6],
		void 0,
		[5],
		void 0
	]);
	assert.equal(await getColumn(99), null, "a property without a part has no column");
});
test("viewer data: a raw array value is a copy the caller may keep", async () => {
	const col = await getColumn(4);
	rawValue(col, 0).push(42);
	assert.deepEqual(rawValue(col, 0), [5, 6]);
});
function writtenOneByOne(col, type, n) {
	const out = makeColumn(propertyKind(type), n);
	for (let r = 0; r < n; r++) {
		const value = rawValue(col, r);
		if (out.kind === "numeric") out.data[r] = numericCell(value, type === PropertyType.date);
		else if (out.kind === "bool") out.data[r] = boolCell(value);
		else if (out.kind === "string") out.data[r] = value ?? null;
		else out.sparse[r] = Array.isArray(value) ? value : null;
	}
	return out;
}
test("viewer data: toColumnData stores every value like writeSlot, for every encoding and type", async () => {
	const types = [
		PropertyType.number,
		PropertyType.date,
		PropertyType.checkbox,
		PropertyType.string,
		PropertyType.multi_tags,
		PropertyType._folders,
		PropertyType.color
	];
	for (const id of [
		1,
		2,
		3,
		4
	]) {
		const col = await getColumn(id);
		for (const type of types) {
			const got = toColumnData(col, type);
			const want = writtenOneByOne(col, type, 4);
			const label = `${col.enc} column as ${type}`;
			assert.equal(got.kind, want.kind, label);
			if (got.kind === "tag" && want.kind === "tag") {
				assert.deepEqual(got.sparse, want.sparse, label);
				if (got.csr) assert.deepEqual(got.csr, buildCSR(got.sparse, 4), label + ": csr");
			} else if (got.kind === "string" && want.kind === "string") assert.deepEqual(got.data, want.data, label);
			else if (got.kind !== "tag" && want.kind !== "tag") {
				assert.ok([...got.data].every((v, i) => Object.is(v, want.data[i])), label);
				assert.equal(got.data.length, 4, label);
			}
		}
	}
});
test("viewer data: a date string becomes its timestamp in a numeric column", async () => {
	const got = toColumnData(await getColumn(3), PropertyType.date);
	assert.equal(got.kind, "numeric");
	if (got.kind === "numeric") assert.equal(got.data[0], Date.parse("2024-09-01T00:00:00Z"));
});
test("viewer data: maps come back in the backend flat layout", async () => {
	assert.deepEqual(await getMapData(3), [
		"cc33",
		.5,
		-1,
		"aa11",
		3,
		4.25
	]);
});
test("viewer data: a map pyramid, with its tile URLs and its points without a thumbnail", async () => {
	const m = await getManifest();
	assert.deepEqual(getMapPyramid(m.maps[0]), {
		order: 1,
		levels: [64],
		tile: 1024,
		url: "map/3/{cell}/{x}_{y}.jpg",
		missing: [1]
	});
	assert.equal(getMapPyramid(m.maps[1]), void 0, "a map without points has none");
});
test("viewer data: image URLs pick a rendition like /image/by_size", async () => {
	await getManifest();
	assert.equal(imageUrl("aa11", 100), "img/1/aa/aa11.jpg", "smallest at least that big");
	assert.equal(imageUrl("aa11", 256), "img/1/aa/aa11.jpg");
	assert.equal(imageUrl("aa11", 300), "img/2/aa/aa11.jpg");
	assert.equal(imageUrl("aa11", 5e3), "img/9/aa/aa11.png", "a full-size type covers any size");
	assert.equal(imageUrl("aa11"), "img/9/aa/aa11.png", "no size: the largest");
	assert.equal(imageUrl(""), "");
});
test("viewer data: a part that failed to load can be loaded again", async () => {
	await assert.rejects(loadPart("late"));
	files["late"] = { ok: true };
	assert.deepEqual(await loadPart("late"), { ok: true });
	assert.equal(g.__panopticData.late, void 0, "the payload does not stay on window");
});
//#endregion
export {};
