//! Project schema the engine reads: properties, tags (with the derived hierarchy) and folders.
//!
//! Mirrors the frontend `dataStore` indexes. The tag hierarchy is derived exactly as
//! `buildTagTree` + `getTagChildren` / `getTagParents` do it (deterministic cycle breaking,
//! DFS orders preserved), because the order of `allParents` decides group creation order.

use std::collections::{BTreeMap, HashSet};

use rustc_hash::{FxHashMap, FxHashSet};
use serde::{Deserialize, Serialize};

pub type PropId = i64;
pub type TagId = i32;
pub type FolderId = i64;
pub type InstanceId = i32;

/// `PropertyType` of `src/data/models/property.ts` (serde names = the JSON strings).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PropertyType {
    #[serde(rename = "multi_tags")]
    MultiTags,
    #[serde(rename = "tag")]
    Tag,
    #[serde(rename = "text")]
    Text,
    #[serde(rename = "number")]
    Number,
    #[serde(rename = "date")]
    Date,
    #[serde(rename = "color")]
    Color,
    #[serde(rename = "url")]
    Url,
    #[serde(rename = "checkbox")]
    Checkbox,
    #[serde(rename = "path")]
    Path,
    #[serde(rename = "image_link")]
    ImageLink,
    #[serde(rename = "ahash")]
    Ahash,
    #[serde(rename = "sha1")]
    Sha1,
    #[serde(rename = "folder")]
    Folder,
    #[serde(rename = "id")]
    Id,
    #[serde(rename = "width")]
    Width,
    #[serde(rename = "height")]
    Height,
    #[serde(other)]
    Unknown,
}

impl PropertyType {
    pub fn is_tag(self) -> bool {
        matches!(self, PropertyType::Tag | PropertyType::MultiTags)
    }

    /// Storage kind, as `propertyKind` in `src/data/lib/columns.ts`.
    pub fn kind(self) -> ColumnKind {
        use PropertyType::*;
        match self {
            Number | Date | Color | Width | Height | Id => ColumnKind::Num,
            Checkbox => ColumnKind::Bool,
            MultiTags | Tag => ColumnKind::Tags,
            // A folder column holds folder ids. The TS store keeps them in a generic (string
            // kind) array; numbers are the only thing ever written there, so a numeric column
            // with "generic" read semantics is equivalent (see Snapshot::is_fast_numeric).
            Folder => ColumnKind::Num,
            _ => ColumnKind::Str,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ColumnKind {
    Num,
    Bool,
    Str,
    Tags,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum PropertyMode {
    Sha1,
    #[default]
    Id,
    File,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PropertyDef {
    pub id: PropId,
    #[serde(default)]
    pub name: String,
    #[serde(rename = "type", alias = "dtype")]
    pub ptype: PropertyType,
    #[serde(default)]
    pub mode: PropertyMode,
    #[serde(default)]
    pub system_key: Option<String>,
    /// A deleted property (the TS store tombstones it with `deletedID`): filters, sorts and
    /// group levels on it are dropped, as `verifyState` does.
    #[serde(default)]
    pub deleted: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TagDef {
    pub id: TagId,
    pub property_id: PropId,
    pub value: String,
    #[serde(default)]
    pub parents: Vec<TagId>,
    #[serde(default)]
    pub color: Option<i64>,
    #[serde(default)]
    pub deleted: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FolderDef {
    pub id: FolderId,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub parent: Option<FolderId>,
    #[serde(default)]
    pub path: Option<String>,
}

/// The ids of the system properties backed by the identity columns.
#[derive(Debug, Clone, Copy, Default)]
pub struct SystemProps {
    pub instance_id: Option<PropId>,
    pub sha1: Option<PropId>,
    pub file_id: Option<PropId>,
    pub folder: Option<PropId>,
}

/// Derived hierarchy data for one tag.
#[derive(Debug, Clone, Default)]
pub struct TagTree {
    pub effective_parents: Vec<TagId>,
    pub ignored_parents: Vec<TagId>,
    pub children: Vec<TagId>,
    /// Ancestors in `getTagParents` DFS order.
    pub all_parents: Vec<TagId>,
    /// Descendants (self excluded).
    pub all_children: FxHashSet<TagId>,
}

/// Immutable project schema. Rebuild with [`Schema::new`] on any change (cheap: proportional to
/// the number of properties + tags).
#[derive(Debug, Clone, Default)]
pub struct Schema {
    pub properties: BTreeMap<PropId, PropertyDef>,
    pub tags: BTreeMap<TagId, TagDef>,
    pub folders: BTreeMap<FolderId, FolderDef>,
    pub system: SystemProps,
    tree: FxHashMap<TagId, TagTree>,
    /// property id → (tag id → `{self} ∪ allParents`, in `new Set(allParents).add(self)` order)
    /// for the property's live tags. The grouping expansion table (`tagWithParents`).
    expand: FxHashMap<PropId, FxHashMap<TagId, Vec<TagId>>>,
}

impl Schema {
    pub fn new(
        properties: impl IntoIterator<Item = PropertyDef>,
        tags: impl IntoIterator<Item = TagDef>,
        folders: impl IntoIterator<Item = FolderDef>,
    ) -> Self {
        let properties: BTreeMap<_, _> = properties.into_iter().map(|p| (p.id, p)).collect();
        let tags: BTreeMap<_, _> = tags.into_iter().map(|t| (t.id, t)).collect();
        let folders: BTreeMap<_, _> = folders.into_iter().map(|f| (f.id, f)).collect();
        let mut system = SystemProps::default();
        for p in properties.values() {
            match p.system_key.as_deref() {
                Some("id") => system.instance_id = Some(p.id),
                Some("sha1") => system.sha1 = Some(p.id),
                Some("file_id") => system.file_id = Some(p.id),
                Some("folder") => system.folder = Some(p.id),
                _ => {}
            }
        }
        let mut s = Schema { properties, tags, folders, system, tree: FxHashMap::default(), expand: FxHashMap::default() };
        s.build_tag_trees();
        s
    }

    pub fn property(&self, id: PropId) -> Option<&PropertyDef> {
        self.properties.get(&id)
    }

    /// The property exists and is not deleted (what `verifyState` keeps).
    pub fn live_property(&self, id: PropId) -> Option<&PropertyDef> {
        self.properties.get(&id).filter(|p| !p.deleted)
    }

    pub fn tag(&self, id: TagId) -> Option<&TagDef> {
        self.tags.get(&id)
    }

    pub fn tag_tree(&self, id: TagId) -> Option<&TagTree> {
        self.tree.get(&id)
    }

    /// `tagWithParents` of a tag property: tag → its expansion (`allParents` then self), for the
    /// live tags whose `propertyId` is `prop`.
    pub fn tag_expansion(&self, prop: PropId) -> Option<&FxHashMap<TagId, Vec<TagId>>> {
        self.expand.get(&prop)
    }

    /// Label of a tag as `property.tags[id].value` reads it (the property's own registry; a
    /// deleted tag keeps its key there and reads as its stored value).
    pub fn tag_label_in(&self, prop: PropId, id: TagId) -> Option<&str> {
        self.tags.get(&id).filter(|t| t.property_id == prop).map(|t| t.value.as_str())
    }

    pub fn folder_name(&self, id: FolderId) -> Option<&str> {
        self.folders.get(&id).map(|f| f.name.as_str())
    }

    fn build_tag_trees(&mut self) {
        // buildTagTree, per property, over the property's live tags sorted by id.
        let mut by_prop: BTreeMap<PropId, Vec<TagId>> = BTreeMap::new();
        for t in self.tags.values() {
            if !t.deleted {
                by_prop.entry(t.property_id).or_default().push(t.id);
            }
        }
        let mut tree: FxHashMap<TagId, TagTree> = FxHashMap::default();
        for ids in by_prop.values() {
            // ids are already ascending (BTreeMap iteration order).
            for &id in ids {
                tree.insert(id, TagTree::default());
            }
            for &id in ids {
                let mut parents: Vec<TagId> = self.tags[&id].parents.clone();
                parents.sort_unstable();
                parents.dedup();
                for parent_id in parents {
                    if parent_id == id || parent_id <= 0 {
                        continue;
                    }
                    match self.tags.get(&parent_id) {
                        Some(p) if !p.deleted => {}
                        _ => continue,
                    }
                    // A parent in another property is still accepted by buildTagTree (it reads the
                    // property's index only through `tags[parentId]`, which is that index): it is
                    // not there, so it is dropped as dangling.
                    if !tree.contains_key(&parent_id) || self.tags[&parent_id].property_id != self.tags[&id].property_id {
                        continue;
                    }
                    if reaches(&tree, parent_id, id) {
                        tree.get_mut(&id).unwrap().ignored_parents.push(parent_id);
                        continue;
                    }
                    tree.get_mut(&id).unwrap().effective_parents.push(parent_id);
                    tree.get_mut(&parent_id).unwrap().children.push(id);
                }
            }
        }
        // getTagChildren / getTagParents for every live tag.
        let live: Vec<TagId> = tree.keys().copied().collect();
        for id in live {
            let all_children = tag_children(&tree, id);
            let all_parents = tag_parents(&tree, &self.tags, id);
            let t = tree.get_mut(&id).unwrap();
            t.all_children = all_children;
            t.all_parents = all_parents;
        }
        let mut expand: FxHashMap<PropId, FxHashMap<TagId, Vec<TagId>>> = FxHashMap::default();
        for t in self.tags.values() {
            if t.deleted {
                continue;
            }
            let tt = &tree[&t.id];
            let mut v = Vec::with_capacity(tt.all_parents.len() + 1);
            let mut seen = HashSet::new();
            for &p in &tt.all_parents {
                if seen.insert(p) {
                    v.push(p);
                }
            }
            if seen.insert(t.id) {
                v.push(t.id);
            }
            expand.entry(t.property_id).or_default().insert(t.id, v);
        }
        self.tree = tree;
        self.expand = expand;
    }
}

fn reaches(tree: &FxHashMap<TagId, TagTree>, from: TagId, target: TagId) -> bool {
    let mut stack = vec![from];
    let mut seen = FxHashSet::default();
    while let Some(cur) = stack.pop() {
        if cur == target {
            return true;
        }
        if !seen.insert(cur) {
            continue;
        }
        if let Some(t) = tree.get(&cur) {
            stack.extend_from_slice(&t.effective_parents);
        }
    }
    false
}

/// getTagChildren minus the tag itself.
fn tag_children(tree: &FxHashMap<TagId, TagTree>, id: TagId) -> FxHashSet<TagId> {
    let mut res = FxHashSet::default();
    let mut seen = FxHashSet::default();
    let mut stack = vec![id];
    while let Some(t) = stack.pop() {
        let Some(node) = tree.get(&t) else { continue };
        if !seen.insert(t) {
            continue;
        }
        if t != id {
            res.insert(t);
        }
        for &c in &node.children {
            stack.push(c);
        }
    }
    res
}

/// getTagParents: DFS over effective parents, stack order preserved.
fn tag_parents(tree: &FxHashMap<TagId, TagTree>, tags: &BTreeMap<TagId, TagDef>, id: TagId) -> Vec<TagId> {
    let mut res = Vec::new();
    let mut seen = FxHashSet::default();
    seen.insert(id);
    let mut stack: Vec<TagId> = tree.get(&id).map(|t| t.effective_parents.clone()).unwrap_or_default();
    while let Some(p) = stack.pop() {
        if p <= 0 || seen.contains(&p) {
            continue;
        }
        match tags.get(&p) {
            Some(t) if !t.deleted => {}
            _ => continue,
        }
        seen.insert(p);
        res.push(p);
        if let Some(t) = tree.get(&p) {
            stack.extend_from_slice(&t.effective_parents);
        }
    }
    res
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tag(id: TagId, parents: &[TagId]) -> TagDef {
        TagDef { id, property_id: 1, value: format!("t{id}"), parents: parents.to_vec(), color: None, deleted: false }
    }

    #[test]
    fn hierarchy_breaks_cycles_deterministically() {
        // 1 <- 2 <- 3, and 1 claims 3 as parent (a cycle): the edge with the larger child id
        // sorted first wins, so 1 -> 3 is examined first (child 1) and accepted, then 2 -> 1
        // (child 2) accepted, then 3 -> 2 would close the loop and is ignored.
        let s = Schema::new([], [tag(1, &[3]), tag(2, &[1]), tag(3, &[2])], []);
        assert_eq!(s.tag_tree(1).unwrap().effective_parents, vec![3]);
        assert_eq!(s.tag_tree(2).unwrap().effective_parents, vec![1]);
        assert_eq!(s.tag_tree(3).unwrap().ignored_parents, vec![2]);
        assert_eq!(s.tag_tree(2).unwrap().all_parents, vec![1, 3]);
        assert!(s.tag_tree(3).unwrap().all_children.contains(&2));
    }
}
