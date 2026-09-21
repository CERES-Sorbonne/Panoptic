"""Undo / redo stack semantics.

``test_data_db.py`` covers the *resolver*: what the state becomes when a given commit is
enabled or disabled. This file covers the layer above it — which commit undo and redo pick,
per author, and which commits are allowed on the stacks at all:

* undo is LIFO over your own enabled commits, redo is its mirror;
* a new edit ends an undone branch — the commits it superseded leave the redo stack, so redo
  can never re-enable a commit a later edit has already overwritten (that is what produced a
  history full of undos that changed nothing);
* a write that asserts the state the DB already holds makes no commit at all, for the same
  reason: every entry in the history must be an entry whose undo does something.
"""
import json
import random

import pytest

from panoptic.core.databases.data.create import GENESIS_COMMIT_ID
from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.data.models import (
    ChangeOp, DataCommit, Instance, InstanceValue, Property, Sha1Value, Tag,
)
from panoptic.core.databases.data.resolver import ENTITY_SPECS, resolve
from panoptic.core.databases.entity_schema import OP_CREATE, OP_UPDATE, OP_DELETE
from panoptic.models.models import PropertyType

NUM = 10          # number property, instance mode
TAGS = 20         # multi_tags property, instance mode
MONO = 30         # tag property (holds at most one tag), instance mode
SHA_TAGS = 40     # multi_tags property, sha1 mode


class Db:
    """Thin harness: edits, reads and stacks in the shape the tests talk about."""

    def __init__(self, path):
        self.writer = DataWriter(str(path)); self.writer.start()
        self.reader = DataReader(str(path)); self.reader.start()
        self.writer.add_structural(instances=[Instance(id=1, file_id=1, sha1='a'),
                                              Instance(id=2, file_id=2, sha1='b')])
        # Authorless setup commit: it belongs to no user's stack, so no test undoes into it.
        self.setup = self.writer.apply_commit('system', DataCommit(properties=[
            _prop(NUM, 'number'),
            _prop(TAGS, PropertyType.multi_tags.value),
            _prop(MONO, PropertyType.tag.value),
            _prop(SHA_TAGS, PropertyType.multi_tags.value, mode='sha1'),
        ])).id

    def close(self):
        self.writer.close(); self.reader.close()

    # --- edits ---------------------------------------------------------
    def set_num(self, value, author='u1', instance=1):
        return self.writer.apply_commit('ui', DataCommit(instance_values=[
            InstanceValue(property_id=NUM, instance_id=instance, value=value,
                          operation=OP_UPDATE)]), author=author)

    def set_tags(self, tag_ids, author='u1', instance=1, prop=TAGS):
        return self.writer.apply_commit('ui', DataCommit(instance_values=[
            InstanceValue(property_id=prop, instance_id=instance, value=list(tag_ids),
                          operation=OP_UPDATE)]), author=author)

    def set_sha1_tags(self, tag_ids, author='u1', sha1='a'):
        return self.writer.apply_commit('ui', DataCommit(sha1_values=[
            Sha1Value(property_id=SHA_TAGS, sha1=sha1, value=list(tag_ids),
                      operation=OP_UPDATE)]), author=author)

    def add_tag(self, tag_id, value='t', author='u1', list_id=TAGS):
        return self.writer.apply_commit('ui', DataCommit(tags=[
            Tag(id=tag_id, list_id=list_id, value=value, color=0, parents=[],
                operation=OP_CREATE)]), author=author)

    def delete_tag(self, tag_id, author='u1'):
        return self.writer.apply_commit('ui', DataCommit(
            tags=[Tag(id=tag_id, operation=OP_DELETE)]), author=author)

    def rename_prop(self, name, author='u1', pid=NUM):
        return self.writer.apply_commit('ui', DataCommit(properties=[
            Property(id=pid, dtype='number', mode='id', name=name, access='write',
                     tag_list_id=pid, operation=OP_UPDATE)]), author=author)

    # --- reads ---------------------------------------------------------
    def num(self, instance=1):
        rows = self.reader.get_instance_values(property_id=NUM, instance_id=instance)
        return rows[0].value if rows else None

    def tags(self, instance=1, prop=TAGS):
        return sorted(v.tag_id for v in
                      self.reader.get_instance_tag_values(property_id=prop, instance_id=instance))

    def sha1_tags(self, sha1='a'):
        return sorted(v.tag_id for v in
                      self.reader.get_sha1_tag_values(property_id=SHA_TAGS, sha1=sha1))

    def prop_name(self, pid=NUM):
        rows = self.reader.get_properties(id=pid)
        return rows[0].name if rows else None

    # --- stacks --------------------------------------------------------
    def undo(self, author='u1'):
        return self.writer.undo(author)

    def redo(self, author='u1'):
        return self.writer.redo(author)

    def stacks(self, author='u1', all_authors=False):
        undo, redo = self.reader.get_undo_redo(author=author, all_authors=all_authors)
        return [c.id for c in undo], [c.id for c in redo]

    def commit_ids(self):
        return sorted(c.id for c in self.reader.get_commits())

    def state(self):
        """Everything the tests look at, as one comparable snapshot."""
        return (self.num(1), self.num(2), self.tags(), self.tags(prop=MONO),
                self.sha1_tags(), self.prop_name(),
                sorted(t.id for t in self.reader.get_tags()))

    def walk_undo(self):
        """Undo to the bottom of the stack, asserting every step changes something.

        This is the user-facing promise: pressing ctrl+Z always does something visible. It
        holds for a single author, whose newest commit is the newest one enabled on every cell
        it touched; another author's later edit can legitimately shadow yours.
        """
        steps = []
        while True:
            before = self.state()
            commit = self.undo()
            if commit is None:
                return steps
            assert self.state() != before, f'undo of commit {commit.id} changed nothing'
            steps.append(commit.id)

    def walk_redo(self):
        """Redo to the top of the stack, asserting every step changes something."""
        steps = []
        while True:
            before = self.state()
            commit = self.redo()
            if commit is None:
                return steps
            assert self.state() != before, f'redo of commit {commit.id} changed nothing'
            steps.append(commit.id)

    def shadowed_commits(self):
        """Commits whose enabled bit decides nothing at all any more.

        Re-resolves every entity the commit touched with its bit flipped and reports the ones
        where nothing moves. A commit shadowed by a *newer* one is normal (undo pops the newer
        one first); two commits asserting the same thing on the same cell are not, and that is
        what left the history with an undo that did nothing.
        """
        active = {c.id: c.active for c in self.reader.get_commits()}
        active[GENESIS_COMMIT_ID] = 1
        dead = []
        with self.writer.transaction() as tx:
            for cid in sorted(active):
                if cid == GENESIS_COMMIT_ID:
                    continue
                keys = tx.execute("SELECT DISTINCT entity_type, entity_key FROM entity_log"
                                  " WHERE commit_id = ?", (cid,)).fetchall()
                changed = False
                for et, key in keys:
                    spec = ENTITY_SPECS[et]
                    ops = [ChangeOp(et, key, r[0], r[1], json.loads(r[2]) if r[2] else None)
                           for r in tx.execute(
                               "SELECT commit_id, op, changes FROM entity_log"
                               " WHERE entity_type = ? AND entity_key = ? ORDER BY commit_id",
                               (et, key))]
                    now = resolve(spec, key, [o for o in ops if active.get(o.commit, 0)])
                    flip = resolve(spec, key, [o for o in ops
                                               if (active.get(o.commit, 0) == 1) != (o.commit == cid)])
                    if now != flip:
                        changed = True
                        break
                if not changed:
                    dead.append(cid)
        return dead


def _prop(pid, dtype, mode='id', name=None):
    return Property(id=pid, dtype=dtype, mode=mode, name=name or f'p{pid}',
                    access='write', tag_list_id=pid, operation=OP_CREATE)


@pytest.fixture
def db(tmp_path):
    d = Db(tmp_path / 'data.db')
    yield d
    d.close()


# ---------------------------------------------------------------------------
# Stack basics
# ---------------------------------------------------------------------------

def test_nothing_to_undo_or_redo_on_an_untouched_history(db):
    assert db.undo() is None
    assert db.redo() is None
    assert db.stacks() == ([], [])


def test_undo_is_lifo_over_your_own_commits(db):
    a, b, c = db.set_num(1), db.set_num(2), db.set_num(3)
    assert db.num() == 3

    assert db.undo().id == c.id
    assert db.num() == 2
    assert db.undo().id == b.id
    assert db.num() == 1
    assert db.undo().id == a.id
    assert db.num() is None
    assert db.undo() is None


def test_redo_mirrors_undo(db):
    a, b, c = db.set_num(1), db.set_num(2), db.set_num(3)
    db.undo(); db.undo()
    assert db.num() == 1

    assert db.redo().id == b.id
    assert db.num() == 2
    assert db.redo().id == c.id
    assert db.num() == 3
    assert db.redo() is None
    assert db.stacks() == ([a.id, b.id, c.id], [])


def test_undo_all_then_redo_all_round_trips(db):
    db.set_num(1); db.set_tags([1, 2]); db.rename_prop('renamed'); db.set_num(7)
    before = (db.num(), db.tags(), db.prop_name())

    while db.undo() is not None:
        pass
    assert (db.num(), db.tags(), db.prop_name()) == (None, [], 'p10')

    while db.redo() is not None:
        pass
    assert (db.num(), db.tags(), db.prop_name()) == before


def test_stacks_track_each_toggle(db):
    a, b, c = db.set_num(1), db.set_num(2), db.set_num(3)
    assert db.stacks() == ([a.id, b.id, c.id], [])

    db.undo()
    assert db.stacks() == ([a.id, b.id], [c.id])
    db.undo()
    assert db.stacks() == ([a.id], [b.id, c.id])
    db.redo()
    assert db.stacks() == ([a.id, b.id], [c.id])


def test_undo_never_reaches_the_genesis_baseline(db):
    db.set_num(1)
    db.undo()
    assert db.undo() is None
    assert GENESIS_COMMIT_ID not in db.commit_ids()


# ---------------------------------------------------------------------------
# Per-author stacks
# ---------------------------------------------------------------------------

def test_undo_only_touches_your_own_commits(db):
    mine = db.set_num(1, author='u1')
    theirs = db.set_num(2, author='u2')

    assert db.undo(author='u1').id == mine.id      # not the newer commit of u2
    assert db.num() == 2                            # u2's value still wins
    assert db.undo(author='u1') is None
    assert db.undo(author='u2').id == theirs.id
    assert db.num() is None


def test_redo_only_touches_your_own_commits(db):
    db.set_num(1, author='u1')
    db.set_num(2, author='u2')
    db.undo(author='u2')

    assert db.redo(author='u1') is None
    assert db.redo(author='u2') is not None
    assert db.num() == 2


def test_authorless_commits_are_not_on_a_users_stack(db):
    """Imports, plugins and system writes carry no author: no user can undo them."""
    db.writer.apply_commit('import', DataCommit(instance_values=[
        InstanceValue(property_id=NUM, instance_id=1, value=5, operation=OP_UPDATE)]))

    assert db.stacks(author='u1') == ([], [])
    assert db.undo(author='u1') is None
    # …the authorless caller itself still has one, which is what the plugin API undoes with.
    assert db.undo(author=None) is not None
    assert db.num() is None


def test_history_scope_all_lists_every_author(db):
    a = db.set_num(1, author='u1')
    b = db.set_num(2, author='u2')
    db.undo(author='u2')

    assert db.stacks(author='u1') == ([a.id], [])
    # scope=all is the project-wide, display-only list: every author, plus the authorless
    # commits (imports, plugins, system) that no user's stack holds.
    assert db.stacks(author='u1', all_authors=True) == ([db.setup, a.id], [b.id])


# ---------------------------------------------------------------------------
# A new edit ends the undone branch  (the bug seen in the field)
# ---------------------------------------------------------------------------

def test_new_edit_after_an_undo_clears_the_redo_stack(db):
    db.set_num(1)
    undone = db.undo()
    assert db.stacks() == ([], [undone.id])

    fresh = db.set_num(9)
    assert db.stacks() == ([fresh.id], [])
    assert db.redo() is None


def test_a_superseded_commit_never_comes_back_through_redo(db):
    db.set_num(1)
    db.set_num(2)
    db.undo()                     # back to 1
    db.set_num(3)                 # new branch: the commit that set 2 is gone for good

    assert db.redo() is None
    assert db.num() == 3
    db.undo()
    assert db.num() == 1          # not 2
    db.undo()
    assert db.num() is None


def test_removing_a_tag_twice_around_an_undo_leaves_no_dead_undo(db):
    """The field scenario: remove a tag, ctrl+Z, remove it again, ctrl+shift+Z, ctrl+Z.

    The last undo used to do nothing: redo had re-enabled the first removal, so two enabled
    DELETE ops sat on the same cell and disabling either one left the other in charge.
    """
    db.add_tag(7, 'B')
    db.set_sha1_tags([7])
    assert db.sha1_tags() == [7]

    db.set_sha1_tags([])          # remove the tag
    assert db.sha1_tags() == []
    db.undo()                     # ctrl+Z -> the tag is back
    assert db.sha1_tags() == [7]
    db.set_sha1_tags([])          # remove it again, by hand
    assert db.sha1_tags() == []

    assert db.redo() is None      # the first removal is not redoable any more
    db.undo()                     # ctrl+Z -> the tag really comes back
    assert db.sha1_tags() == [7]
    assert db.shadowed_commits() == []


def test_undoing_the_new_edit_puts_it_back_on_the_redo_stack(db):
    db.set_num(1)
    db.undo()
    fresh = db.set_num(9)

    undone = db.undo()
    assert undone.id == fresh.id
    assert db.stacks() == ([], [fresh.id])
    assert db.redo().id == fresh.id       # the new edit, never the discarded one
    assert db.num() == 9


def test_discarding_is_per_author(db):
    db.set_num(1, author='u1')
    db.undo(author='u1')
    db.set_num(2, author='u2')            # somebody else's edit

    assert db.redo(author='u1') is not None   # u1's redo survives u2's work
    assert db.stacks(author='u2') == ([c for c in db.commit_ids() if c][-1:], [])


def test_only_the_discarded_branch_leaves_the_stack(db):
    keep = db.set_num(1)
    db.set_num(2)
    db.undo()                              # undo the 2
    fresh = db.set_num(3)                  # discards the 2

    assert db.stacks() == ([keep.id, fresh.id], [])


# ---------------------------------------------------------------------------
# A write that changes nothing makes no commit
# ---------------------------------------------------------------------------

def test_setting_the_same_value_makes_no_commit(db):
    first = db.set_num(5)
    assert db.set_num(5) is None
    assert db.commit_ids() == [db.setup, first.id]
    assert db.stacks() == ([first.id], [])

    db.undo()
    assert db.num() is None


def test_setting_the_same_value_on_a_cleared_cell_does_commit(db):
    """The skip is about the *alive* row: once the cell is empty, re-setting is a real change."""
    db.set_num(5)
    db.undo()
    again = db.set_num(5)
    assert again is not None
    assert db.num() == 5


def test_unchanged_property_update_makes_no_commit(db):
    db.rename_prop('renamed')
    before = db.commit_ids()
    assert db.rename_prop('renamed') is None
    assert db.commit_ids() == before


def test_deleting_what_is_already_deleted_makes_no_commit(db):
    db.add_tag(7)
    first = db.delete_tag(7)
    assert first is not None
    assert db.delete_tag(7) is None
    assert db.stacks()[0][-1] == first.id

    db.undo()
    assert [t.id for t in db.reader.get_tags(id=7)] == [7]


def test_re_removing_a_tag_that_is_already_gone_makes_no_commit(db):
    db.add_tag(7)
    db.set_tags([7])
    db.set_tags([])
    before = db.commit_ids()
    assert db.set_tags([]) is None
    assert db.commit_ids() == before


def test_a_real_change_among_no_ops_still_commits(db):
    db.set_num(5)
    commit = db.writer.apply_commit('ui', DataCommit(instance_values=[
        InstanceValue(property_id=NUM, instance_id=1, value=5, operation=OP_UPDATE),   # no-op
        InstanceValue(property_id=NUM, instance_id=2, value=8, operation=OP_UPDATE),   # real
    ]), author='u1')

    assert commit is not None
    assert (db.num(1), db.num(2)) == (5, 8)
    db.undo()
    assert (db.num(1), db.num(2)) == (5, None)   # only the real change is reverted


def test_every_undo_in_a_long_session_does_something(db):
    """The user-facing promise: ctrl+Z always changes something on screen."""
    db.add_tag(1, 'a'); db.add_tag(2, 'b')
    db.set_num(1); db.set_num(2)
    db.set_tags([1]); db.set_tags([1, 2]); db.set_tags([2])
    db.undo(); db.set_tags([1, 2])
    db.rename_prop('x'); db.rename_prop('y')
    db.undo(); db.undo(); db.redo()
    db.set_num(3)

    end = db.state()
    undone = db.walk_undo()
    assert undone == sorted(undone, reverse=True)      # LIFO
    assert db.walk_redo() == sorted(undone)
    assert db.state() == end


# ---------------------------------------------------------------------------
# What the stacks do to real data
# ---------------------------------------------------------------------------

def test_tag_assignment_round_trip(db):
    db.add_tag(1); db.add_tag(2)
    db.set_tags([1])
    db.set_tags([1, 2])
    db.set_tags([2])
    assert db.tags() == [2]

    db.undo(); assert db.tags() == [1, 2]
    db.undo(); assert db.tags() == [1]
    db.undo(); assert db.tags() == []
    db.redo(); assert db.tags() == [1]
    db.redo(); assert db.tags() == [1, 2]
    db.redo(); assert db.tags() == [2]


def test_mono_tag_round_trip(db):
    db.set_tags([1], prop=MONO)
    db.set_tags([2], prop=MONO)
    db.set_tags([3], prop=MONO)
    assert db.tags(prop=MONO) == [3]

    db.undo(); assert db.tags(prop=MONO) == [2]
    db.undo(); assert db.tags(prop=MONO) == [1]
    db.redo(); assert db.tags(prop=MONO) == [2]
    db.redo(); assert db.tags(prop=MONO) == [3]


def test_undo_of_a_tag_deletion_restores_its_assignments(db):
    db.add_tag(1); db.set_tags([1])
    db.delete_tag(1)
    assert db.tags() == []

    db.undo()
    assert db.tags() == [1]
    assert [t.id for t in db.reader.get_tags(id=1)] == [1]


def test_undo_of_a_property_creation_hides_its_values_and_redo_restores_them(db):
    create = db.writer.apply_commit('ui', DataCommit(
        properties=[_prop(50, 'text')]), author='u1')
    db.writer.apply_commit('ui', DataCommit(instance_values=[
        InstanceValue(property_id=50, instance_id=1, value='hello', operation=OP_UPDATE)]),
        author='u2')

    db.writer.set_commit_active(create.id, False)
    assert db.reader.get_properties(id=50) == []
    db.writer.set_commit_active(create.id, True)
    assert db.reader.get_properties(id=50)[0].name == 'p50'
    assert db.reader.get_instance_values(property_id=50)[0].value == 'hello'


# ---------------------------------------------------------------------------
# Commit timeline + compaction
# ---------------------------------------------------------------------------

def test_timeline_disable_puts_a_commit_on_the_redo_stack(db):
    a = db.set_num(1)
    db.set_num(2)

    db.writer.set_commit_active(a.id, False)     # disabled from the Data settings timeline
    assert db.stacks()[1] == [a.id]
    assert db.redo().id == a.id


def test_compaction_empties_the_stacks_behind_the_horizon(db):
    a = db.set_num(1)
    b = db.set_num(2)
    db.writer.compact(b.id)

    assert db.stacks() == ([], [])
    assert db.undo() is None
    assert db.num() == 2                          # the folded state stays

    c = db.set_num(3)
    assert db.stacks() == ([c.id], [])
    db.undo()
    assert db.num() == 2                          # falls back on the baseline


def test_compaction_drops_an_undone_commit_from_the_redo_stack(db):
    db.set_num(1)
    undone = db.undo()
    db.writer.compact(undone.id)

    assert db.stacks() == ([], [])
    assert db.redo() is None
    assert db.num() is None                       # the undone commit folded out, not in


# ---------------------------------------------------------------------------
# Several users at once
# ---------------------------------------------------------------------------

def test_users_undo_their_own_work_independently(db):
    db.set_num(1, author='u1', instance=1)
    db.set_num(2, author='u2', instance=2)
    db.rename_prop('from-u1', author='u1')

    db.undo(author='u1')                          # the rename
    assert db.prop_name() == 'p10'
    assert (db.num(1), db.num(2)) == (1, 2)

    db.undo(author='u2')
    assert (db.num(1), db.num(2)) == (1, None)
    db.undo(author='u1')
    assert (db.num(1), db.num(2)) == (None, None)


def test_two_users_deleting_the_same_cell_both_have_to_undo(db):
    """Two authors can each own a delete of the same cell, and then one undo is not enough.

    This needs a genuine overlap — u2 removing a tag their screen still shows, before u1's
    delta arrives — which a single user can no longer produce (that was the field bug). Here
    it is staged by disabling u1's commit while u2's is written. State is the fold of the
    enabled set, so u2's undo leaves u1's delete in charge; neither may revert the other's op.
    """
    db.add_tag(7)
    db.set_sha1_tags([7])

    def remove(author):
        return db.writer.apply_commit('ui', DataCommit(sha1_values=[
            Sha1Value(property_id=SHA_TAGS, sha1='a', value=[], operation=OP_UPDATE)]),
            author=author)

    first = remove('u1')
    db.writer.set_commit_active(first.id, False)      # u2 is still looking at the tag
    second = remove('u2')
    db.writer.set_commit_active(first.id, True)       # …and u1's delete lands after all
    assert second is not None and second.id != first.id

    assert db.sha1_tags() == []
    db.undo(author='u2')
    assert db.sha1_tags() == []                   # u1's delete still holds
    db.undo(author='u1')
    assert db.sha1_tags() == [7]


def test_one_users_edit_does_not_disturb_the_others_stack(db):
    a = db.set_num(1, author='u1')
    db.undo(author='u1')
    for i in range(3):
        db.set_num(10 + i, author='u2')

    assert db.stacks(author='u1') == ([], [a.id])
    assert db.redo(author='u1').id == a.id


# ---------------------------------------------------------------------------
# Randomised sessions against a reference model
# ---------------------------------------------------------------------------

class Model:
    """What the stacks and the cell value should be, expressed without any SQL."""

    def __init__(self):
        self.commits = []          # {'id', 'author', 'value', 'active', 'redoable'}
        self.next_id = 2           # 1 is the property-creation commit of the fixture

    def value(self):
        live = [c for c in self.commits if c['active']]
        return max(live, key=lambda c: c['id'])['value'] if live else None

    def edit(self, author, value):
        if value == self.value():
            return None            # asserting the current state is not a change
        for c in self.commits:
            if c['author'] == author and not c['active']:
                c['redoable'] = False
        self.commits.append({'id': self.next_id, 'author': author, 'value': value,
                             'active': True, 'redoable': True})
        self.next_id += 1
        return self.commits[-1]['id']

    def undo(self, author):
        live = [c for c in self.commits if c['active'] and c['author'] == author]
        if not live:
            return None
        c = max(live, key=lambda c: c['id'])
        c['active'], c['redoable'] = False, True
        return c['id']

    def redo(self, author):
        dead = [c for c in self.commits
                if not c['active'] and c['redoable'] and c['author'] == author]
        if not dead:
            return None
        c = min(dead, key=lambda c: c['id'])
        c['active'] = True
        return c['id']

    def stacks(self, author):
        mine = sorted((c for c in self.commits if c['author'] == author), key=lambda c: c['id'])
        return ([c['id'] for c in mine if c['active']],
                [c['id'] for c in mine if not c['active'] and c['redoable']])


@pytest.mark.parametrize('seed', range(12))
def test_random_session_matches_the_model(tmp_path, seed):
    rng = random.Random(seed)
    db = Db(tmp_path / f'fuzz{seed}.db')
    model = Model()
    authors = ['u1', 'u2']
    try:
        for step in range(60):
            author = rng.choice(authors)
            action = rng.choices(['edit', 'undo', 'redo'], weights=[5, 3, 3])[0]
            if action == 'edit':
                value = rng.randrange(4)
                got = db.set_num(value, author=author)
                want = model.edit(author, value)
                assert (got.id if got else None) == want, f'seed {seed} step {step} edit'
            elif action == 'undo':
                got = db.undo(author)
                assert (got.id if got else None) == model.undo(author), \
                    f'seed {seed} step {step} undo'
            else:
                got = db.redo(author)
                assert (got.id if got else None) == model.redo(author), \
                    f'seed {seed} step {step} redo'

            assert db.num() == model.value(), f'seed {seed} step {step} value'
            for a in authors:
                assert db.stacks(a) == model.stacks(a), f'seed {seed} step {step} stacks {a}'
        # Undoing everything must still walk out cleanly, one visible change at a time.
        for author in authors:
            while db.undo(author) is not None:
                pass
        assert db.num() is None, f'seed {seed}: undoing everything left a value behind'
    finally:
        db.close()


@pytest.mark.parametrize('seed', range(8))
def test_random_session_undoes_all_the_way_back(tmp_path, seed):
    """Whatever the session did, undoing everything returns to the starting state, and redoing
    everything from there returns to where the undos began."""
    rng = random.Random(seed)
    db = Db(tmp_path / f'rewind{seed}.db')
    try:
        for _ in range(40):
            action = rng.choices(['num', 'tags', 'rename', 'undo', 'redo'],
                                 weights=[4, 4, 2, 3, 2])[0]
            if action == 'num':
                db.set_num(rng.randrange(4))
            elif action == 'tags':
                db.set_tags(sorted(rng.sample([1, 2, 3], rng.randrange(4))))
            elif action == 'rename':
                db.rename_prop(f'n{rng.randrange(3)}')
            elif action == 'undo':
                db.undo()
            else:
                db.redo()

        db.walk_redo()                                 # bring back whatever is still undone
        end = db.state()

        undone = db.walk_undo()                        # every undo changes something
        assert (db.num(), db.tags(), db.prop_name()) == (None, [], 'p10')

        assert db.walk_redo() == sorted(undone)        # …and so does every redo
        assert db.state() == end
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Schema migration for the redo bit
# ---------------------------------------------------------------------------

def test_v1_database_gains_the_redoable_column(tmp_path):
    """A data DB written before the redo stack existed opens with every commit redoable."""
    path = tmp_path / 'old.db'
    db = Db(path)
    db.set_num(1)
    db.undo()
    db.close()

    # Rewind the file to what v1 looked like: no `redoable` column, version 1.
    import sqlite3
    con = sqlite3.connect(path)
    con.execute("ALTER TABLE commits DROP COLUMN redoable")
    con.execute("UPDATE _version SET value = 1 WHERE key = 'db_version'")
    con.commit(); con.close()

    writer = DataWriter(str(path)); writer.start()
    try:
        with writer.transaction() as tx:
            rows = tx.execute("SELECT id, active, redoable FROM commits ORDER BY id").fetchall()
        assert rows and all(r[2] == 1 for r in rows)
        assert writer.redo('u1') is not None      # the undone commit is redoable again
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# The routes the frontend actually calls
# ---------------------------------------------------------------------------

@pytest.fixture
def project(tmp_path):
    from panoptic.core.project.project import Project
    p = Project(tmp_path / 'proj')
    p.start()
    yield p
    p.close()


def _body(response):
    """The routes answer with a serialized Response; read the payload back out of it."""
    return json.loads(response.body)


def _set_value(project, value, user_id='u1', prop=None):
    from panoptic.routes.project_routes import UpsertRequest, upsert_commit_route
    req = UpsertRequest(instance_values=[
        {'property_id': prop, 'instance_id': 1, 'value': value}])
    return upsert_commit_route(req, project, user_id=user_id)


def _new_prop(project):
    from panoptic.routes.project_routes import UpsertRequest, upsert_commit_route
    res = upsert_commit_route(
        UpsertRequest(properties=[{'id': -1, 'name': 'note', 'type': 'text'}]),
        project, user_id='u1')
    return res['properties'][0]['id']


def test_routes_undo_redo_and_history(project):
    from fastapi import HTTPException
    from panoptic.routes.project_routes import get_history, redo_route, undo_route

    pid = _new_prop(project)
    _set_value(project, 'a', prop=pid)
    _set_value(project, 'b', prop=pid)

    history = _body(get_history(project, user_id='u1'))
    assert len(history['undo']) == 3 and history['redo'] == []      # property + 2 values
    assert all(e['own'] for e in history['undo'])

    undo_route(project, user_id='u1')
    history = _body(get_history(project, user_id='u1'))
    assert len(history['undo']) == 2 and len(history['redo']) == 1

    redo_route(project, user_id='u1')
    assert len(_body(get_history(project, user_id='u1'))['redo']) == 0

    # Another user has nothing of their own, on either stack.
    other = _body(get_history(project, user_id='u2'))
    assert other == {'undo': [], 'redo': []}
    with pytest.raises(HTTPException) as e:
        undo_route(project, user_id='u2')
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        redo_route(project, user_id='u2')
    assert e.value.status_code == 400


def test_routes_new_edit_clears_the_redo_stack(project):
    from fastapi import HTTPException
    from panoptic.routes.project_routes import get_history, redo_route, undo_route

    pid = _new_prop(project)
    _set_value(project, 'a', prop=pid)
    undo_route(project, user_id='u1')
    assert len(_body(get_history(project, user_id='u1'))['redo']) == 1

    _set_value(project, 'c', prop=pid)
    assert _body(get_history(project, user_id='u1'))['redo'] == []
    with pytest.raises(HTTPException):
        redo_route(project, user_id='u1')


def test_routes_scope_all_shows_other_authors(project):
    from panoptic.routes.project_routes import get_history

    pid = _new_prop(project)
    _set_value(project, 'a', user_id='u1', prop=pid)
    _set_value(project, 'b', user_id='u2', prop=pid)

    mine = _body(get_history(project, user_id='u1', scope='own'))
    everyone = _body(get_history(project, user_id='u1', scope='all'))
    assert len(mine['undo']) == 2                     # the property + u1's value
    # Everyone's list adds u2's value and the authorless commit the project writes at
    # creation (the system properties), which belongs to no user's stack.
    assert [(e['source'], e['own']) for e in everyone['undo']] == [
        ('system', False), ('ui', True), ('ui', True), ('ui', False)]


def test_routes_repeated_identical_write_adds_no_history(project):
    from panoptic.routes.project_routes import get_history

    pid = _new_prop(project)
    _set_value(project, 'same', prop=pid)
    before = len(_body(get_history(project, user_id='u1'))['undo'])
    _set_value(project, 'same', prop=pid)
    assert len(_body(get_history(project, user_id='u1'))['undo']) == before
