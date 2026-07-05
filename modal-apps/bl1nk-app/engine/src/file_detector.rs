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

#[cfg(test)]
mod tests {
    use super::*;

    fn files(paths: &[&str]) -> Vec<String> {
        paths.iter().map(|p| p.to_string()).collect()
    }

    #[test]
    fn test_detects_rust_language() {
        let result = FileDetector::detect(&files(&["src/main.rs"]));
        assert!(result.contains(&"lang:rust".to_string()));
    }

    #[test]
    fn test_detects_python_language() {
        let result = FileDetector::detect(&files(&["app.py"]));
        assert!(result.contains(&"lang:python".to_string()));
    }

    #[test]
    fn test_detects_node_language_for_js_and_ts() {
        let result = FileDetector::detect(&files(&["index.js", "types.ts"]));
        assert!(result.contains(&"lang:node".to_string()));
    }

    #[test]
    fn test_detects_test_type_and_stage() {
        let result = FileDetector::detect(&files(&["tests/foo.rs"]));
        assert!(result.contains(&"type:test".to_string()));
        assert!(result.contains(&"stage:test".to_string()));
        assert!(result.contains(&"lang:rust".to_string()));
    }

    #[test]
    fn test_detects_docs_from_directory() {
        let result = FileDetector::detect(&files(&["docs/guide.txt"]));
        assert!(result.contains(&"type:docs".to_string()));
    }

    #[test]
    fn test_detects_docs_from_markdown_extension() {
        let result = FileDetector::detect(&files(&["README.md"]));
        assert!(result.contains(&"type:docs".to_string()));
    }

    #[test]
    fn test_detects_dependency_files() {
        let cargo = FileDetector::detect(&files(&["Cargo.toml"]));
        assert!(cargo.contains(&"type:dep".to_string()));

        let package = FileDetector::detect(&files(&["package.json"]));
        assert!(package.contains(&"type:dep".to_string()));
    }

    #[test]
    fn test_empty_file_list_returns_empty() {
        let result = FileDetector::detect(&files(&[]));
        assert!(result.is_empty());
    }

    #[test]
    fn test_deduplicates_labels_across_files() {
        let result = FileDetector::detect(&files(&["src/a.rs", "src/b.rs"]));
        assert_eq!(result.iter().filter(|l| *l == "lang:rust").count(), 1);
    }
}
