# TODO - modal-opencode/engine (sovereign_engine)

## Missing Tests
- [ ] src/lib.rs: add Rust unit tests for resolve_full_state()
- [ ] src/detector.rs: add tests for regex pattern matching
- [ ] src/file_detector.rs: add tests for file extension detection
- [ ] src/resolver.rs: add tests for label resolution logic (exclusive groups, defaults)
- [ ] src/policy.rs: add tests for policy enforcement (blocking, stage guardrail, dep check)
- [ ] src/size_calc.rs: add tests for PR size calculation

## Code Issues
- [ ] resolver.rs: exclusive_groups should be a constant, not recreated per call
- [ ] detector.rs: regex patterns hardcoded — should be configurable
- [ ] No benchmarks for engine performance
