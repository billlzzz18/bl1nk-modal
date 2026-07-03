use std::collections::HashSet;

pub struct PolicyEngine;

impl PolicyEngine {
    pub fn enforce(labels: &mut HashSet<String>, changed_files: &Vec<String>) {
        // 1. Priority Escalation: ถ้ามี label 'blocking' หรือ 'auto:blocking' ให้ปรับเป็น p:p0 ทันที
        if labels.iter().any(|l| l.contains("blocking")) {
            labels.retain(|l| !l.starts_with("p:"));
            labels.insert("p:p0".to_string());
        }

        // 2. State Guardrail: ถ้ามีการแก้ไฟล์โค้ด (.rs, .py) แต่พยายามย้ายไป 'stage:finalize' 
        // โดยที่ยังไม่มี 'rev:ready' ให้ดึงกลับมาที่ 'stage:review'
        let has_code_changes = changed_files.iter().any(|f| f.ends_with(".rs") || f.ends_with(".py"));
        let is_finalizing = labels.contains("stage:finalize");
        let is_approved = labels.contains("rev:ready");

        if has_code_changes && is_finalizing && !is_approved {
            labels.remove("stage:finalize");
            labels.insert("stage:review".to_string());
            labels.insert("auto:wait".to_string()); // เพิ่ม label บอกว่ารอการอนุมัติ
        }

        // 3. Dependency Check: ถ้าแก้ไฟล์ config ของโปรเจกต์ ต้องมี 'type:dep'
        if changed_files.iter().any(|f| f.contains("Cargo.toml") || f.contains("package.json")) {
            labels.insert("type:dep".to_string());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn label_set(items: &[&str]) -> HashSet<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    fn files(items: &[&str]) -> Vec<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn test_blocking_label_escalates_priority_to_p0() {
        let mut labels = label_set(&["p:p2", "blocking"]);
        PolicyEngine::enforce(&mut labels, &files(&[]));
        assert!(labels.contains("p:p0"));
        assert!(!labels.contains("p:p2"));
    }

    #[test]
    fn test_auto_blocking_label_also_escalates_priority() {
        let mut labels = label_set(&["p:p3", "auto:blocking"]);
        PolicyEngine::enforce(&mut labels, &files(&[]));
        assert!(labels.contains("p:p0"));
    }

    #[test]
    fn test_no_escalation_without_blocking_label() {
        let mut labels = label_set(&["p:p1"]);
        PolicyEngine::enforce(&mut labels, &files(&[]));
        assert!(labels.contains("p:p1"));
    }

    #[test]
    fn test_guardrail_pulls_back_finalize_when_code_changed_and_not_approved() {
        let mut labels = label_set(&["stage:finalize"]);
        PolicyEngine::enforce(&mut labels, &files(&["src/lib.rs"]));
        assert!(!labels.contains("stage:finalize"));
        assert!(labels.contains("stage:review"));
        assert!(labels.contains("auto:wait"));
    }

    #[test]
    fn test_guardrail_allows_finalize_when_approved() {
        let mut labels = label_set(&["stage:finalize", "rev:ready"]);
        PolicyEngine::enforce(&mut labels, &files(&["src/lib.rs"]));
        assert!(labels.contains("stage:finalize"));
        assert!(!labels.contains("auto:wait"));
    }

    #[test]
    fn test_guardrail_ignores_non_code_changes() {
        let mut labels = label_set(&["stage:finalize"]);
        PolicyEngine::enforce(&mut labels, &files(&["docs/readme.md"]));
        assert!(labels.contains("stage:finalize"));
        assert!(!labels.contains("auto:wait"));
    }

    #[test]
    fn test_dependency_check_flags_cargo_toml() {
        let mut labels = HashSet::new();
        PolicyEngine::enforce(&mut labels, &files(&["Cargo.toml"]));
        assert!(labels.contains("type:dep"));
    }

    #[test]
    fn test_dependency_check_flags_package_json() {
        let mut labels = HashSet::new();
        PolicyEngine::enforce(&mut labels, &files(&["frontend/package.json"]));
        assert!(labels.contains("type:dep"));
    }

    #[test]
    fn test_dependency_check_ignores_unrelated_files() {
        let mut labels = HashSet::new();
        PolicyEngine::enforce(&mut labels, &files(&["src/main.rs"]));
        assert!(!labels.contains("type:dep"));
    }
}
