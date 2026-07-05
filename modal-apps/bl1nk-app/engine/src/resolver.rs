use std::collections::HashSet;
use crate::policy::PolicyEngine;

pub struct Resolver;

impl Resolver {
    pub fn resolve(
        detected: Vec<String>,
        manual_add: Vec<String>,
        manual_remove: Vec<String>,
        current: Vec<String>,
        changed_files: Vec<String>,
    ) -> Vec<String> {
        let mut final_labels: HashSet<String> = current.into_iter().collect();

        // 1. จัดการการลบแบบ Manual
        for label in manual_remove {
            final_labels.remove(&label);
        }

        // 2. เพิ่ม Label ที่ตรวจพบอัตโนมัติ (Detected + File-Aware)
        for label in detected {
            Self::add_exclusive(&mut final_labels, label);
        }

        // 3. จัดการการเพิ่มแบบ Manual (มีอำนาจเหนือการตรวจอัตโนมัติ)
        for label in manual_add {
            Self::add_exclusive(&mut final_labels, label);
        }

        // 4. บังคับใช้นโยบายของโปรเจกต์ (Policy Enforcement)
        PolicyEngine::enforce(&mut final_labels, &changed_files);

        // 5. ใส่ค่า Default สำหรับกลุ่มที่จำเป็น
        Self::ensure_defaults(&mut final_labels);

        let mut sorted: Vec<String> = final_labels.into_iter().collect();
        sorted.sort();
        sorted
    }

    fn add_exclusive(labels: &mut HashSet<String>, new_label: String) {
        if let Some((prefix, _)) = new_label.split_once(':') {
            let prefix = prefix.trim();
            // Mutually exclusive groups
            let exclusive_groups = ["stage", "type", "p", "size", "lang", "env", "plat", "rev"];
            if exclusive_groups.contains(&prefix) {
                // Remove existing labels with the same prefix
                labels.retain(|l| !l.starts_with(&format!("{}:", prefix)));
            }
        }
        labels.insert(new_label);
    }

    fn ensure_defaults(labels: &mut HashSet<String>) {
        // Defaults from labels.json
        if !labels.iter().any(|l| l.starts_with("stage:")) {
            labels.insert("stage:spec".to_string());
        }
        if !labels.iter().any(|l| l.starts_with("size:")) {
            labels.insert("size:m".to_string());
        }
        if !labels.iter().any(|l| l.starts_with("p:")) {
            labels.insert("p:p1".to_string());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn strings(items: &[&str]) -> Vec<String> {
        items.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn test_detected_label_replaces_existing_in_exclusive_group() {
        let result = Resolver::resolve(
            strings(&["stage:test"]),
            vec![],
            vec![],
            strings(&["stage:plan"]),
            vec![],
        );
        assert!(result.contains(&"stage:test".to_string()));
        assert!(!result.contains(&"stage:plan".to_string()));
    }

    #[test]
    fn test_manual_remove_deletes_current_label() {
        let result = Resolver::resolve(vec![], vec![], strings(&["p:p2"]), strings(&["p:p2"]), vec![]);
        assert!(!result.contains(&"p:p2".to_string()));
        // Default priority kicks back in once p:p2 is gone.
        assert!(result.contains(&"p:p1".to_string()));
    }

    #[test]
    fn test_manual_add_overrides_detected_in_exclusive_group() {
        let result = Resolver::resolve(strings(&["type:feat"]), strings(&["type:fix"]), vec![], vec![], vec![]);
        assert!(result.contains(&"type:fix".to_string()));
        assert!(!result.contains(&"type:feat".to_string()));
    }

    #[test]
    fn test_non_exclusive_labels_are_not_removed() {
        let result = Resolver::resolve(strings(&["rev:ready"]), vec![], vec![], vec![], vec![]);
        assert!(result.contains(&"rev:ready".to_string()));
    }

    #[test]
    fn test_ensure_defaults_fills_missing_groups() {
        let result = Resolver::resolve(vec![], vec![], vec![], vec![], vec![]);
        assert!(result.contains(&"stage:spec".to_string()));
        assert!(result.contains(&"size:m".to_string()));
        assert!(result.contains(&"p:p1".to_string()));
    }

    #[test]
    fn test_ensure_defaults_does_not_override_present_groups() {
        let result = Resolver::resolve(vec![], vec![], vec![], strings(&["stage:act", "size:l", "p:p0"]), vec![]);
        assert!(result.contains(&"stage:act".to_string()));
        assert!(result.contains(&"size:l".to_string()));
        assert!(result.contains(&"p:p0".to_string()));
        assert!(!result.contains(&"stage:spec".to_string()));
    }

    #[test]
    fn test_result_is_sorted() {
        let result = Resolver::resolve(strings(&["type:feat", "lang:rust"]), vec![], vec![], vec![], vec![]);
        let mut sorted = result.clone();
        sorted.sort();
        assert_eq!(result, sorted);
    }
}
