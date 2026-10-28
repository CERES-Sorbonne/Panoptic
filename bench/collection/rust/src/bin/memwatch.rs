//! Measures a benchmark process's memory footprint (the number Activity Monitor shows) during one
//! op, leaving out the data load. Runs `cmd args.. --wait`, forwards its stdout, and when the
//! `"meta":true` line arrives (data loaded, GC done, child blocked on stdin) records the current
//! footprint, writes "go", then polls the footprint until the child exits.
//! Prints a last line: {"memwatch":true,"load_footprint":..,"peak_footprint":..,"lifetime_max_footprint":..}
//!
//!   memwatch node --expose-gc js/bench.js --n=1000000 --mem "--op=sort: text"

use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering::Relaxed};
use std::sync::Arc;
use std::time::Duration;

fn usage(pid: i32) -> Option<libc::rusage_info_v4> {
    let mut ri: libc::rusage_info_v4 = unsafe { std::mem::zeroed() };
    let rc = unsafe { libc::proc_pid_rusage(pid, libc::RUSAGE_INFO_V4, &mut ri as *mut _ as *mut libc::rusage_info_t) };
    (rc == 0).then_some(ri)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut child = Command::new(&args[0])
        .args(&args[1..])
        .arg("--wait")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("spawn");
    let pid = child.id() as i32;
    let mut stdin = child.stdin.take().unwrap();
    let stdout = BufReader::new(child.stdout.take().unwrap());

    let peak = Arc::new(AtomicU64::new(0));
    let lifetime = Arc::new(AtomicU64::new(0));
    let polling = Arc::new(AtomicBool::new(false));
    let done = Arc::new(AtomicBool::new(false));
    let poller = {
        let (peak, lifetime, polling, done) = (peak.clone(), lifetime.clone(), polling.clone(), done.clone());
        std::thread::spawn(move || {
            while !done.load(Relaxed) {
                if polling.load(Relaxed) {
                    if let Some(ri) = usage(pid) {
                        peak.fetch_max(ri.ri_phys_footprint, Relaxed);
                        lifetime.store(ri.ri_lifetime_max_phys_footprint, Relaxed);
                    }
                }
                std::thread::sleep(Duration::from_micros(200));
            }
        })
    };

    let mut load = 0;
    let out = std::io::stdout();
    for line in stdout.lines() {
        let line = line.unwrap();
        writeln!(out.lock(), "{line}").unwrap();
        if load == 0 && line.contains(r#""meta":true"#) {
            std::thread::sleep(Duration::from_millis(50));
            load = usage(pid).map_or(0, |ri| ri.ri_phys_footprint);
            peak.store(load, Relaxed);
            polling.store(true, Relaxed);
            stdin.write_all(b"go\n").unwrap();
            stdin.flush().unwrap();
        }
    }
    done.store(true, Relaxed);
    poller.join().unwrap();
    let status = child.wait().unwrap();
    println!(
        r#"{{"memwatch":true,"load_footprint":{load},"peak_footprint":{},"lifetime_max_footprint":{}}}"#,
        peak.load(Relaxed),
        lifetime.load(Relaxed)
    );
    std::process::exit(status.code().unwrap_or(1));
}
