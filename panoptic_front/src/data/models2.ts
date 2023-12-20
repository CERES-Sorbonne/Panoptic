export enum PropertyType {
    multi_tags = "multi_tags",
    tag = "tag",
    string = "string",
    number = "number",
    date = "date",
    color = "color",
    url = "url",


    checkbox = "checkbox",
    path = "path",
    image_link = "image_link",
    _ahash = "average hash",
    _sha1 = "sha1",
    _folders = "folders"
}

export interface Property {
    id: number
    name: string
    type: PropertyType
    mode: PropertyMode
    tags?: TagIndex
}

export enum PropertyMode {
    sha1 = 'sha1',
    id = 'id',
}

export interface TagIndex {
    [tagId: number]: Tag
}

export interface Tag {
    id: number;
    property_id: number;
    parents: number[];
    value: string;
    color?: number;
    children?: Set<number>
    count?: number
}