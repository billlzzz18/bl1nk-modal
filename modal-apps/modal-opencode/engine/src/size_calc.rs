pub struct SizeCalculator;

impl SizeCalculator {
    pub fn calculate_pr_size(additions: i32, deletions: i32) -> String {
        let total = additions + deletions;
        if total <= 50 {
            "xs".to_string()
        } else if total <= 150 {
            "s".to_string()
        } else if total <= 300 {
            "m".to_string()
        } else if total <= 600 {
            "l".to_string()
        } else if total <= 1200 {
            "xl".to_string()
        } else if total <= 3000 {
            "xxl".to_string()
        } else {
            "xxxl".to_string()
        }
    }

    pub fn detect_issue_size(text: &str) -> Option<String> {
        let text = text.to_lowercase();
        if text.contains("xxl") || text.contains("massive") || text.contains("epic") {
            Some("xxl".to_string())
        } else if text.contains("xl") || text.contains("extra-large") || text.contains("huge") {
            Some("xl".to_string())
        } else if text.contains("large") || text.contains("big") || text.contains("major") {
            Some("l".to_string())
        } else if text.contains("medium") || text.contains("mid") || text.contains("moderate") {
            Some("m".to_string())
        } else if text.contains("small") || text.contains("minor") || text.contains("quick") {
            Some("s".to_string())
        } else if text.contains("xs") || text.contains("tiny") || text.contains("trivial") {
            Some("xs".to_string())
        } else {
            None
        }
    }
}
