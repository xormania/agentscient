use std::fs;

use fixture_rust_crate::store::read_records;

#[test]
fn probe() {
    let root = std::env::temp_dir().join(format!("rc05-{}", std::process::id()));
    let unreadable = root.join("unreadable");
    let corrupt = root.join("corrupt");
    fs::create_dir_all(&unreadable).expect("create unreadable store path");
    fs::write(&corrupt, "not-a-record").expect("write corrupt store");
    let unreadable_is_ok = read_records(&unreadable).is_ok();
    let corrupt_is_ok = read_records(&corrupt).is_ok();
    fs::remove_dir_all(root).expect("remove store probes");
    assert!(!unreadable_is_ok && !corrupt_is_ok);
}
