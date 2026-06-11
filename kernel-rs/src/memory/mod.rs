//! Memory Manager — Per-agent isolated memory with hierarchy.

use std::collections::HashMap;

pub struct AgentHeap {
    pub pid: u64,
    data: HashMap<String, Vec<u8>>,
    used_bytes: usize,
    max_bytes: usize,
}

impl AgentHeap {
    pub fn new(pid: u64, max_bytes: usize) -> Self {
        Self {
            pid,
            data: HashMap::new(),
            used_bytes: 0,
            max_bytes,
        }
    }

    pub fn store(&mut self, key: &str, value: Vec<u8>) -> Result<(), &'static str> {
        let size = value.len();
        if self.used_bytes + size > self.max_bytes {
            return Err("Memory limit exceeded");
        }
        if let Some(old) = self.data.insert(key.to_string(), value) {
            self.used_bytes -= old.len();
        }
        self.used_bytes += size;
        Ok(())
    }

    pub fn load(&self, key: &str) -> Option<&Vec<u8>> {
        self.data.get(key)
    }

    pub fn usage(&self) -> (usize, usize) {
        (self.used_bytes, self.max_bytes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_heap_limits() {
        let mut heap = AgentHeap::new(1, 100);
        assert!(heap.store("key1", vec![0u8; 50]).is_ok());
        assert!(heap.store("key2", vec![0u8; 60]).is_err()); // Over limit
        assert_eq!(heap.usage().0, 50);
    }
}
