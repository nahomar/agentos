//! Capability System — Zero ambient authority for agents.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct CapabilityId(pub u64);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Permission {
    Read,
    Write,
    Execute,
    Create,
    Destroy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Capability {
    pub id: CapabilityId,
    pub resource: String,
    pub permissions: Vec<Permission>,
    pub delegatable: bool,
    pub revoked: bool,
    pub owner_pid: u64,
}

pub struct CapabilityManager {
    capabilities: HashMap<CapabilityId, Capability>,
    agent_caps: HashMap<u64, Vec<CapabilityId>>, // pid -> capabilities
    next_id: u64,
}

impl CapabilityManager {
    pub fn new() -> Self {
        Self {
            capabilities: HashMap::new(),
            agent_caps: HashMap::new(),
            next_id: 0,
        }
    }

    pub fn grant(&mut self, pid: u64, resource: &str, perms: Vec<Permission>) -> CapabilityId {
        self.next_id += 1;
        let id = CapabilityId(self.next_id);
        let cap = Capability {
            id,
            resource: resource.to_string(),
            permissions: perms,
            delegatable: false,
            revoked: false,
            owner_pid: pid,
        };
        self.capabilities.insert(id, cap);
        self.agent_caps.entry(pid).or_default().push(id);
        id
    }

    pub fn check(&self, pid: u64, resource: &str, perm: Permission) -> bool {
        let caps = match self.agent_caps.get(&pid) {
            Some(caps) => caps,
            None => return false,
        };

        caps.iter().any(|cap_id| {
            if let Some(cap) = self.capabilities.get(cap_id) {
                !cap.revoked && cap.resource == resource && cap.permissions.contains(&perm)
            } else {
                false
            }
        })
    }

    pub fn revoke(&mut self, cap_id: CapabilityId) {
        if let Some(cap) = self.capabilities.get_mut(&cap_id) {
            cap.revoked = true;
        }
    }

    pub fn revoke_all(&mut self, pid: u64) {
        if let Some(caps) = self.agent_caps.get(&pid) {
            for cap_id in caps.clone() {
                self.revoke(cap_id);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_grant_and_check() {
        let mut mgr = CapabilityManager::new();
        mgr.grant(1, "spotify.play", vec![Permission::Execute]);

        assert!(mgr.check(1, "spotify.play", Permission::Execute));
        assert!(!mgr.check(1, "spotify.play", Permission::Write));
        assert!(!mgr.check(2, "spotify.play", Permission::Execute));
    }

    #[test]
    fn test_revoke() {
        let mut mgr = CapabilityManager::new();
        let cap = mgr.grant(1, "payments.send", vec![Permission::Execute]);

        assert!(mgr.check(1, "payments.send", Permission::Execute));
        mgr.revoke(cap);
        assert!(!mgr.check(1, "payments.send", Permission::Execute));
    }
}
