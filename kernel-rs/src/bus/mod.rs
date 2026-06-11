//! Semantic Bus — Actions as system calls.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RiskLevel {
    Safe,
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionSchema {
    pub id: String,
    pub app_id: String,
    pub name: String,
    pub description: String,
    pub risk_level: RiskLevel,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionResult {
    pub success: bool,
    pub action_id: String,
    pub data: Option<serde_json::Value>,
    pub error: String,
    pub execution_ms: f64,
}

impl ActionResult {
    pub fn ok(action_id: &str, data: serde_json::Value) -> Self {
        Self {
            success: true,
            action_id: action_id.to_string(),
            data: Some(data),
            error: String::new(),
            execution_ms: 0.0,
        }
    }

    pub fn err(action_id: &str, error: &str) -> Self {
        Self {
            success: false,
            action_id: action_id.to_string(),
            data: None,
            error: error.to_string(),
            execution_ms: 0.0,
        }
    }
}
