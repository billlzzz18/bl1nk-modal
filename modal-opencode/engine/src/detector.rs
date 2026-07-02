use regex::Regex;
use std::collections::HashMap;

pub struct Detector {
    patterns: HashMap<String, Vec<(String, Regex)>>,
}

impl Detector {
    pub fn new() -> Self {
        let mut patterns = HashMap::new();

        // Type patterns
        let mut type_p = Vec::new();
        type_p.push(("feat".to_string(), Regex::new(r"(?i)\b(feature|add|new|implement)\b").unwrap()));
        type_p.push(("fix".to_string(), Regex::new(r"(?i)\b(fix|bug|hotfix|patch)\b").unwrap()));
        type_p.push(("refactor".to_string(), Regex::new(r"(?i)\b(refactor|cleanup|optimize)\b").unwrap()));
        type_p.push(("docs".to_string(), Regex::new(r"(?i)\b(doc|docs|documentation|readme)\b").unwrap()));
        type_p.push(("ui".to_string(), Regex::new(r"(?i)\b(ui|ux|design|style|component)\b").unwrap()));
        type_p.push(("migration".to_string(), Regex::new(r"(?i)\b(migration|migrate|upgrade)\b").unwrap()));
        type_p.push(("db".to_string(), Regex::new(r"(?i)\b(db|database|schema|query)\b").unwrap()));
        type_p.push(("sec".to_string(), Regex::new(r"(?i)\b(security|sec|auth|encrypt)\b").unwrap()));
        type_p.push(("task".to_string(), Regex::new(r"(?i)\b(task|chore)\b").unwrap()));
        type_p.push(("stat".to_string(), Regex::new(r"(?i)\b(report|stat|analytics|metric)\b").unwrap()));
        patterns.insert("type".to_string(), type_p);

        // Stage patterns (keyword based as in bash)
        let mut stage_p = Vec::new();
        stage_p.push(("plan".to_string(), Regex::new(r"(?i)\b(plan|planning|spec|specification)\b").unwrap()));
        stage_p.push(("act".to_string(), Regex::new(r"(?i)\b(act|implement|doing|development)\b").unwrap()));
        stage_p.push(("test".to_string(), Regex::new(r"(?i)\b(test|testing|qa)\b").unwrap()));
        stage_p.push(("doc".to_string(), Regex::new(r"(?i)\b(doc|document|documentation)\b").unwrap()));
        stage_p.push(("review".to_string(), Regex::new(r"(?i)\b(review|reviewing)\b").unwrap()));
        stage_p.push(("finalize".to_string(), Regex::new(r"(?i)\b(finalize|finalized|done)\b").unwrap()));
        patterns.insert("stage".to_string(), stage_p);

        // Priority patterns
        let mut p_p = Vec::new();
        p_p.push(("p0".to_string(), Regex::new(r"(?i)\b(p0|critical|urgent|blocker|asap)\b").unwrap()));
        p_p.push(("p1".to_string(), Regex::new(r"(?i)\b(p1|high|important|soon)\b").unwrap()));
        p_p.push(("p2".to_string(), Regex::new(r"(?i)\b(p2|low|minor|later)\b").unwrap()));
        p_p.push(("p3".to_string(), Regex::new(r"(?i)\b(p3|backlog|someday)\b").unwrap()));
        patterns.insert("p".to_string(), p_p);

        // Language
        let mut lang_p = Vec::new();
        lang_p.push(("node".to_string(), Regex::new(r"(?i)\b(node|nodejs)\b").unwrap()));
        lang_p.push(("js".to_string(), Regex::new(r"(?i)\b(javascript|js)\b").unwrap()));
        lang_p.push(("ts".to_string(), Regex::new(r"(?i)\b(typescript|ts)\b").unwrap()));
        lang_p.push(("rust".to_string(), Regex::new(r"(?i)\b(rust|rs)\b").unwrap()));
        lang_p.push(("python".to_string(), Regex::new(r"(?i)\b(python|py)\b").unwrap()));
        patterns.insert("lang".to_string(), lang_p);

        // Env
        let mut env_p = Vec::new();
        env_p.push(("dev".to_string(), Regex::new(r"(?i)\b(dev|development|local|staging)\b").unwrap()));
        env_p.push(("prod".to_string(), Regex::new(r"(?i)\b(prod|production|live)\b").unwrap()));
        env_p.push(("local".to_string(), Regex::new(r"(?i)\b(local|localhost)\b").unwrap()));
        patterns.insert("env".to_string(), env_p);

        // Constraint
        let mut con_p = Vec::new();
        con_p.push(("mobile".to_string(), Regex::new(r"(?i)\b(mobile|mobile-first|responsive|ios|android)\b").unwrap()));
        patterns.insert("constraint".to_string(), con_p);

        // Plat
        let mut plat_p = Vec::new();
        plat_p.push(("vercel".to_string(), Regex::new(r"(?i)\b(vercel|deploy|preview)\b").unwrap()));
        plat_p.push(("ci".to_string(), Regex::new(r"(?i)\b(ci|continuous integration|github actions|jenkins)\b").unwrap()));
        plat_p.push(("github".to_string(), Regex::new(r"(?i)\b(github|gh)\b").unwrap()));
        plat_p.push(("gitlab".to_string(), Regex::new(r"(?i)\b(gitlab|gl)\b").unwrap()));
        patterns.insert("plat".to_string(), plat_p);

        Self { patterns }
    }

    pub fn detect(&self, text: &str, category: &str) -> Option<String> {
        if let Some(cat_patterns) = self.patterns.get(category) {
            for (label, regex) in cat_patterns {
                if regex.is_match(text) {
                    return Some(label.clone());
                }
            }
        }
        None
    }
}
