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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calculate_pr_size_boundaries() {
        assert_eq!(SizeCalculator::calculate_pr_size(30, 20), "xs"); // 50
        assert_eq!(SizeCalculator::calculate_pr_size(30, 21), "s"); // 51
        assert_eq!(SizeCalculator::calculate_pr_size(100, 50), "s"); // 150
        assert_eq!(SizeCalculator::calculate_pr_size(100, 51), "m"); // 151
        assert_eq!(SizeCalculator::calculate_pr_size(150, 150), "m"); // 300
        assert_eq!(SizeCalculator::calculate_pr_size(150, 151), "l"); // 301
        assert_eq!(SizeCalculator::calculate_pr_size(300, 300), "l"); // 600
        assert_eq!(SizeCalculator::calculate_pr_size(300, 301), "xl"); // 601
        assert_eq!(SizeCalculator::calculate_pr_size(600, 600), "xl"); // 1200
        assert_eq!(SizeCalculator::calculate_pr_size(600, 601), "xxl"); // 1201
        assert_eq!(SizeCalculator::calculate_pr_size(1500, 1500), "xxl"); // 3000
        assert_eq!(SizeCalculator::calculate_pr_size(1500, 1501), "xxxl"); // 3001
    }

    #[test]
    fn test_calculate_pr_size_zero() {
        assert_eq!(SizeCalculator::calculate_pr_size(0, 0), "xs");
    }

    #[test]
    fn test_detect_issue_size_xxl_keywords() {
        assert_eq!(SizeCalculator::detect_issue_size("this is massive"), Some("xxl".to_string()));
        assert_eq!(SizeCalculator::detect_issue_size("an epic saga"), Some("xxl".to_string()));
    }

    #[test]
    fn test_detect_issue_size_xl_keywords() {
        assert_eq!(SizeCalculator::detect_issue_size("extra-large task"), Some("xl".to_string()));
        assert_eq!(SizeCalculator::detect_issue_size("this is huge"), Some("xl".to_string()));
    }

    #[test]
    fn test_detect_issue_size_l_keywords() {
        assert_eq!(SizeCalculator::detect_issue_size("a large change"), Some("l".to_string()));
        assert_eq!(SizeCalculator::detect_issue_size("major rewrite"), Some("l".to_string()));
    }

    #[test]
    fn test_detect_issue_size_m_keywords() {
        assert_eq!(SizeCalculator::detect_issue_size("medium effort"), Some("m".to_string()));
        assert_eq!(SizeCalculator::detect_issue_size("moderate scope"), Some("m".to_string()));
    }

    #[test]
    fn test_detect_issue_size_s_keywords() {
        assert_eq!(SizeCalculator::detect_issue_size("quick fix"), Some("s".to_string()));
        assert_eq!(SizeCalculator::detect_issue_size("minor tweak"), Some("s".to_string()));
    }

    #[test]
    fn test_detect_issue_size_xs_keywords() {
        assert_eq!(SizeCalculator::detect_issue_size("trivial change"), Some("xs".to_string()));
        assert_eq!(SizeCalculator::detect_issue_size("a tiny patch"), Some("xs".to_string()));
    }

    #[test]
    fn test_detect_issue_size_is_case_insensitive() {
        assert_eq!(SizeCalculator::detect_issue_size("MASSIVE REWRITE"), Some("xxl".to_string()));
    }

    #[test]
    fn test_detect_issue_size_no_match_returns_none() {
        assert_eq!(SizeCalculator::detect_issue_size("nothing special here"), None);
    }

    #[test]
    fn test_detect_issue_size_prioritizes_xxl_over_xl() {
        // "xxl" also contains the substring "xl"; xxl must win.
        assert_eq!(SizeCalculator::detect_issue_size("this is xxl"), Some("xxl".to_string()));
    }
}
