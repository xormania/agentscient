use fixture_rust_crate::interval::Interval;

#[test]
fn probe() {
    assert!(!Interval::new(1, 3).contains(3));
}
