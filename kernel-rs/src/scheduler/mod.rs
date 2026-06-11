//! Agent Scheduler — Multi-Level Feedback Queue

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Priority {
    System = 0,
    Interactive = 1,
    Normal = 2,
    Background = 3,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProcessState {
    Created,
    Ready,
    Running,
    Blocked,
    Terminated,
}

#[derive(Debug)]
pub struct Process {
    pub pid: u64,
    pub name: String,
    pub state: ProcessState,
    pub priority: Priority,
    pub run_count: u64,
    pub total_cpu_ms: f64,
}

pub struct Scheduler {
    processes: HashMap<u64, Process>,
    max_concurrent: usize,
    next_pid: u64,
}

impl Scheduler {
    pub fn new(max_concurrent: usize) -> Self {
        Self {
            processes: HashMap::new(),
            max_concurrent,
            next_pid: 1000,
        }
    }

    pub fn spawn(&mut self, name: &str, priority: Priority) -> u64 {
        self.next_pid += 1;
        let pid = self.next_pid;
        self.processes.insert(pid, Process {
            pid,
            name: name.to_string(),
            state: ProcessState::Created,
            priority,
            run_count: 0,
            total_cpu_ms: 0.0,
        });
        pid
    }

    pub fn set_state(&mut self, pid: u64, state: ProcessState) {
        if let Some(proc) = self.processes.get_mut(&pid) {
            proc.state = state;
        }
    }

    pub fn get_runnable(&self) -> Vec<u64> {
        let mut ready: Vec<_> = self.processes.values()
            .filter(|p| p.state == ProcessState::Ready)
            .collect();
        ready.sort_by_key(|p| p.priority);
        ready.iter().take(self.max_concurrent).map(|p| p.pid).collect()
    }

    pub fn process_count(&self) -> usize {
        self.processes.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_spawn_and_schedule() {
        let mut sched = Scheduler::new(2);
        let p1 = sched.spawn("agent1", Priority::Normal);
        let p2 = sched.spawn("agent2", Priority::System);
        let p3 = sched.spawn("agent3", Priority::Background);

        sched.set_state(p1, ProcessState::Ready);
        sched.set_state(p2, ProcessState::Ready);
        sched.set_state(p3, ProcessState::Ready);

        let runnable = sched.get_runnable();
        assert_eq!(runnable.len(), 2); // max_concurrent = 2
        assert_eq!(runnable[0], p2);   // System priority first
    }
}
