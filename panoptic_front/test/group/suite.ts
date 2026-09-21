/**
 * Grouping / clustering regression suite — one bundle, one node:test process.
 *
 * Each spec locks in one fix from the grouping rework; a failure names the regression that came
 * back. See README.md for the fix -> test map and how to run it.
 */
import './harness/hooks'

import './specs/a1_valueParser'
import './specs/a2_version'
import './specs/a3_groupSlots'
import './specs/a4_iterators'
import './specs/a5_staticChecks'
import './specs/a6_setAsRoot'
import './specs/a7_isCurrent'
import './specs/a8_sha1Piles'
import './specs/a9_imageToGroups'
import './specs/a10_deadNodes'
import './specs/a11_clusterRuns'
import './specs/a12_newArrivals'

import './specs/b2_orderSlots'
import './specs/b4_sha1PileScope'
import './specs/b5_resync'
import './specs/b6b7_keysAndPruning'

import './specs/c_simFindings'
import './specs/d1_tagRegistry'
import './specs/d2_tagDeletion'
import './specs/e1_appendLevel'

import './specs/invariants'
import './specs/sim_smoke'
