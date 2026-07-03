use pyo3::prelude::*;

pub mod detector;
pub mod size_calc;
pub mod resolver;
pub mod file_detector;
pub mod policy;

use detector::Detector;
use size_calc::SizeCalculator;
use resolver::Resolver;
use file_detector::FileDetector;

#[pyfunction]
fn resolve_full_state(
    title: String,
    body: String,
    additions: i32,
    deletions: i32,
    changed_files: Vec<String>,
    current_labels: Vec<String>,
    manual_add: Vec<String>,
    manual_remove: Vec<String>,
) -> Vec<String> {
    let detector = Detector::new();
    let full_text = format!("{} {}", title, body);
    
    let mut detected = Vec::new();

    // 1. ตรวจจากข้อความ (Regex)
    if let Some(t) = detector.detect(&full_text, "type") { detected.push(format!("type:{}", t)); }
    if let Some(s) = detector.detect(&full_text, "stage") { detected.push(format!("stage:{}", s)); }
    if let Some(p) = detector.detect(&full_text, "p") { detected.push(format!("p:{}", p)); }

    for cat in ["lang", "env", "constraint", "plat"] {
        if let Some(val) = detector.detect(&full_text, cat) {
            detected.push(format!("{}:{}", cat, val));
        }
    }

    // 2. ตรวจจากไฟล์ที่แก้ (File-Aware)
    let file_labels = FileDetector::detect(&changed_files);
    detected.extend(file_labels);

    // 3. คำนวณขนาดงาน
    let size = if additions >= 0 || deletions >= 0 {
        SizeCalculator::calculate_pr_size(additions, deletions)
    } else {
        SizeCalculator::detect_issue_size(&full_text).unwrap_or("m".to_string())
    };
    detected.push(format!("size:{}", size));

    // 4. สรุปผลผ่าน Resolver และบังคับใช้นโยบาย (Policy)
    Resolver::resolve(detected, manual_add, manual_remove, current_labels, changed_files)
}

#[pymodule]
fn sovereign_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(resolve_full_state, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_file_aware_and_policy() {
        // จำลองสถานการณ์: แก้ไฟล์ .rs (ต้องได้ lang:rust) และ Cargo.toml (ต้องได้ type:dep)
        let title = "update stuff".to_string();
        let changed_files = vec!["src/main.rs".to_string(), "Cargo.toml".to_string()];
        
        let result = resolve_full_state(
            title, "".to_string(), 10, 5, changed_files, vec![], vec![], vec![]
        );
        
        assert!(result.contains(&"lang:rust".to_string()));
        assert!(result.contains(&"type:dep".to_string()));
    }

    #[test]
    fn test_policy_guardrail() {
        // จำลองสถานการณ์: พยายามข้ามไป stage:finalize ทั้งที่ยังไม่พร้อม
        let title = "finish work".to_string();
        let changed_files = vec!["src/lib.rs".to_string()]; // มีการแก้โค้ด
        let manual_add = vec!["stage:finalize".to_string()]; // พยายามย้ายไปจบงาน
        
        let result = resolve_full_state(
            title, "".to_string(), 10, 5, changed_files, vec![], manual_add, vec![]
        );
        
        // ผลลัพธ์: ต้องถูกดึงกลับมาที่ stage:review เพราะมี code change และยังไม่ได้ Approve (rev:ready)
        assert!(result.contains(&"stage:review".to_string()));
        assert!(result.contains(&"auto:wait".to_string()));
        assert!(!result.contains(&"stage:finalize".to_string()));
    }
}
