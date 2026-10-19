//! Cooperative cancellation.
//!
//! Every pipeline function takes a [`CancelToken`] and returns `Result<_, Cancelled>`. The
//! token is checked between phases and inside the parallel loops (once per chunk), so a newer
//! request for the same collection can abort an older one quickly ("latest wins").

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

/// The computation was cancelled through its [`CancelToken`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
#[error("computation cancelled")]
pub struct Cancelled;

/// Cheap clonable cancellation flag (an `Arc<AtomicBool>`).
#[derive(Debug, Clone, Default)]
pub struct CancelToken(Arc<AtomicBool>);

impl CancelToken {
    pub fn new() -> Self {
        Self::default()
    }

    /// A token that is never cancelled (tests, synchronous callers).
    pub fn never() -> Self {
        Self::default()
    }

    pub fn cancel(&self) {
        self.0.store(true, Ordering::Relaxed);
    }

    pub fn is_cancelled(&self) -> bool {
        self.0.load(Ordering::Relaxed)
    }

    /// `Err(Cancelled)` once [`cancel`](Self::cancel) has been called.
    #[inline]
    pub fn check(&self) -> Result<(), Cancelled> {
        if self.is_cancelled() { Err(Cancelled) } else { Ok(()) }
    }
}

/// Chunk size used by the parallel loops: big enough to amortise rayon's overhead, small enough
/// to check the token often.
pub(crate) const CHUNK: usize = 1 << 14;

/// Below this many elements the loops run sequentially.
pub(crate) const PAR_THRESHOLD: usize = 1 << 15;
