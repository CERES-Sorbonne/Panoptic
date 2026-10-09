"""Probe non-sequential undo/redo edge cases on the panoptic data layer."""
import sys, os, tempfile
sys.path.insert(0, '/Users/david/Panoptic/panoptic_back')

from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.entity_schema import OP_CREATE, OP_UPDATE, OP_DELETE
from panoptic.core.databases.data.models import (
    Instance, DataCommit, Property, Tag, InstanceValue,
)
from panoptic.models.models import PropertyType

def setup(name):
    path = os.path.join(tempfile.mkdtemp(), f"{name}.db")
    w = DataWriter(path); w.start()
    r = DataReader(path); r.start()
    return w, r

def prop(pid, dtype='text', mode='id', name='p'):
    return Property(id=pid, dtype=dtype, mode=mode, name=name, access='write',
                    tag_list_id=pid, operation=OP_CREATE)

results = []
def check(label, cond, detail=""):
    results.append((label, cond, detail))
    print(f"{'PASS' if cond else 'FAIL'}  {label}  {detail}")

# ---------------------------------------------------------------- 1
# Undo of a CREATE commit: does the entity disappear?
w, r = setup('t1')
c1 = w.apply_commit('userA', DataCommit(properties=[prop(10, name='color')]))
w.set_commit_active(c1.id, False)
props = r.get_properties(id=10)
check("undo-create removes property", props == [], f"got: {props}")

# tag flavor
c2 = w.apply_commit('userA', DataCommit(
    properties=[prop(11, dtype=PropertyType.multi_tags.value)],
))
c3 = w.apply_commit('userA', DataCommit(
    tags=[Tag(id=1, list_id=11, parents=[], value='cat', color=0, operation=OP_CREATE)]))
w.set_commit_active(c3.id, False)
tags = r.get_tags(id=1)
check("undo-create removes tag", tags == [], f"got: {tags}")

# ---------------------------------------------------------------- 2
# Undo of the only value-set commit: does the value disappear?
w, r = setup('t2')
w.add_structural(instances=[Instance(id=1, file_id=1, sha1='A')])
w.apply_commit('userA', DataCommit(properties=[prop(10, dtype='number')]))
c2 = w.apply_commit('userA', DataCommit(
    instance_values=[InstanceValue(property_id=10, instance_id=1, value=42.0, operation=OP_UPDATE)]))
w.set_commit_active(c2.id, False)
vals = r.get_instance_values(property_id=10)
check("undo only value-set removes value", vals == [], f"got: {vals}")

# ---------------------------------------------------------------- 3
# Undo of tag-assignment commit (junction rows)
w, r = setup('t3')
w.add_structural(instances=[Instance(id=1, file_id=1, sha1='A')])
w.apply_commit('u', DataCommit(properties=[prop(10, dtype=PropertyType.multi_tags.value)],
                               tags=[Tag(id=1, list_id=10, parents=[], value='t1', color=0, operation=OP_CREATE)]))
c2 = w.apply_commit('u', DataCommit(
    instance_values=[InstanceValue(property_id=10, instance_id=1, value=[1], operation=OP_UPDATE)]))
w.set_commit_active(c2.id, False)
jv = r.get_instance_tag_values(property_id=10)
check("undo tag-assign removes junction row", all(v.operation == OP_DELETE for v in jv) or jv == [],
      f"got: {jv}")

# ---------------------------------------------------------------- 4
# Cross-user dependency: A creates tag (c1), B assigns it (c2), A undoes c1.
w, r = setup('t4')
w.add_structural(instances=[Instance(id=1, file_id=1, sha1='A')])
w.apply_commit('setup', DataCommit(properties=[prop(10, dtype=PropertyType.multi_tags.value)]))
cA = w.apply_commit('userA', DataCommit(
    tags=[Tag(id=1, list_id=10, parents=[], value='cat', color=0, operation=OP_CREATE)]))
cB = w.apply_commit('userB', DataCommit(
    instance_values=[InstanceValue(property_id=10, instance_id=1, value=[1], operation=OP_UPDATE)]))
w.set_commit_active(cA.id, False)
tags = r.get_tags(id=1)
jv = [v for v in r.get_instance_tag_values(property_id=10) if v.operation == OP_CREATE]
check("undo tag-create: tag gone", tags == [], f"got: {tags}")
check("undo tag-create: no dangling junction rows", jv == [], f"dangling: {jv}")

# ---------------------------------------------------------------- 5
# Full-state update masking: A renames tag (c2), B recolors (c3, carries A's name), A undoes c2.
w, r = setup('t5')
w.apply_commit('setup', DataCommit(properties=[prop(10, dtype=PropertyType.multi_tags.value)]))
w.apply_commit('setup', DataCommit(
    tags=[Tag(id=1, list_id=10, parents=[], value='cat', color=1, operation=OP_CREATE)]))
cA = w.apply_commit('userA', DataCommit(
    tags=[Tag(id=1, list_id=10, parents=[], value='feline', color=1, operation=OP_UPDATE)]))
# user B sends full state as the UI does: current name + new color
cB = w.apply_commit('userB', DataCommit(
    tags=[Tag(id=1, list_id=10, parents=[], value='feline', color=5, operation=OP_UPDATE)]))
w.set_commit_active(cA.id, False)
t = r.get_tags(id=1)[0]
check("undo rename reverts name despite later color change", t.value == 'cat',
      f"got name={t.value!r} color={t.color}")

# ---------------------------------------------------------------- 6
# Undo delete-property restores cascaded tag values (sequential, sanity)
w, r = setup('t6')
w.add_structural(instances=[Instance(id=1, file_id=1, sha1='A')])
w.apply_commit('u', DataCommit(properties=[prop(10, dtype=PropertyType.multi_tags.value)],
                               tags=[Tag(id=1, list_id=10, parents=[], value='t', color=0, operation=OP_CREATE)]))
w.apply_commit('u', DataCommit(
    instance_values=[InstanceValue(property_id=10, instance_id=1, value=[1], operation=OP_UPDATE)]))
cdel = w.apply_commit('u', DataCommit(properties=[Property(id=10, operation=OP_DELETE)]))
w.set_commit_active(cdel.id, False)
tags = r.get_tags(id=1)
jv = [v for v in r.get_instance_tag_values(property_id=10) if v.operation == OP_CREATE]
check("undo property-delete restores tag", len(tags) == 1, f"got: {tags}")
check("undo property-delete restores tag values", len(jv) == 1, f"got: {jv}")

# ---------------------------------------------------------------- 7
# Interleaved junction add/remove across users, non-sequential undo
# c1: A sets {1}; c2: B sets {1,2}; A undoes c1 -> expected {2}
w, r = setup('t7')
w.add_structural(instances=[Instance(id=1, file_id=1, sha1='A')])
w.apply_commit('setup', DataCommit(properties=[prop(10, dtype=PropertyType.multi_tags.value)],
                                   tags=[Tag(id=1, list_id=10, parents=[], value='a', color=0, operation=OP_CREATE),
                                         Tag(id=2, list_id=10, parents=[], value='b', color=0, operation=OP_CREATE)]))
cA = w.apply_commit('userA', DataCommit(
    instance_values=[InstanceValue(property_id=10, instance_id=1, value=[1], operation=OP_UPDATE)]))
cB = w.apply_commit('userB', DataCommit(
    instance_values=[InstanceValue(property_id=10, instance_id=1, value=[1, 2], operation=OP_UPDATE)]))
w.set_commit_active(cA.id, False)
jv = sorted(v.tag_id for v in r.get_instance_tag_values(property_id=10) if v.operation == OP_CREATE)
check("undo A's {1} after B's {1,2} leaves {2}", jv == [2], f"got: {jv}")

# ---------------------------------------------------------------- 8
# Undo then NEW commit on same PK, then redo the undone commit.
# c1 set 42; c2 set 99; undo c2; c3 set 7; redo c2 -> last commit_id order = c3? expected 7 stays
w, r = setup('t8')
w.add_structural(instances=[Instance(id=1, file_id=1, sha1='A')])
w.apply_commit('u', DataCommit(properties=[prop(10, dtype='number')]))
c1 = w.apply_commit('u', DataCommit(instance_values=[InstanceValue(property_id=10, instance_id=1, value=42.0, operation=OP_UPDATE)]))
c2 = w.apply_commit('u', DataCommit(instance_values=[InstanceValue(property_id=10, instance_id=1, value=99.0, operation=OP_UPDATE)]))
w.set_commit_active(c2.id, False)
c3 = w.apply_commit('u', DataCommit(instance_values=[InstanceValue(property_id=10, instance_id=1, value=7.0, operation=OP_UPDATE)]))
w.set_commit_active(c2.id, True)  # redo old commit
v = float(r.get_instance_values(property_id=10)[0].value)
check("redo of older commit does not clobber newer value", v == 7.0, f"got: {v}")

print()
fails = [x for x in results if not x[1]]
print(f"{len(results)-len(fails)}/{len(results)} passed, {len(fails)} failed")
