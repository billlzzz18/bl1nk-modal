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
