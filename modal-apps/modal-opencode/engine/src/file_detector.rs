use std::collections::HashSet;

pub struct FileDetector;

impl FileDetector {
    pub fn detect(changed_files: &Vec<String>) -> Vec<String> {
        let mut detected = HashSet::new();

        for file in changed_files {
            // Detect Language
            if file.ends_with(".rs") { detected.insert("lang:rust".to_string()); }
            else if file.ends_with(".py") { detected.insert("lang:python".to_string()); }
            else if file.ends_with(".js") || file.ends_with(".ts") { detected.insert("lang:node".to_string()); }

            // Detect Type/Stage from paths
            if file.contains("tests/") {
                detected.insert("type:test".to_string());
                detected.insert("stage:test".to_string());
            } else if file.contains("docs/") || file.ends_with(".md") {
                detected.insert("type:docs".to_string());
            } else if file.contains("Cargo.toml") || file.contains("package.json") {
                detected.insert("type:dep".to_string());
            }
        }

        detected.into_iter().collect()
    }
}
