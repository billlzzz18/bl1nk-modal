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
