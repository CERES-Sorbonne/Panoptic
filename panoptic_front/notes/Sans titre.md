
1. No-sha1 slots — today they silently vanish in sha1Mode (groupBySha1:677 drops them). Drop or singleton-pile? This is a behavioral decision, not just mechanical.
2. Sequencing — do Phase 1 before the cluster mission, or fold it all into the compose refactor?
3. Pile storage — side map (recommended, keeps Group pure) vs fields on the node.
4. Does sha1 piling apply inside cluster groups? It does today; confirming this decides whether the final sweep targets all leaves or property leaves only.
5. isSha1Group vs display piling — keep the two flags fully separate.
6. Persisted view state — confirm nothing reads/persists a pile's view.closed before deleting the old sha1 group index entries.
7. Render-key stability — confirm no recycler key depends on the old sha1 group's valueIndex id.

1 what are the sha1 slots and what are they used for. What are the implication of each choice ?

2 group, insert/update custom groups, apply sha1Mode.

3,4,5 it should stay a flat array of instances. It will be the responsability of the different scrollers to show the images in piles instead of all images of same sha1. The scrollers could know how to show it be reading a flag in the result object. in terms of performance we could also add a array field we the index of each first sha1. So that the scroller can avoid comparing all sha1 and know exactly where to look for the 3 pile in the group for example it would be images from index[3] to index[4]

6,7 dont worry about the scrollers for now we try to find the best way in terms of performance 