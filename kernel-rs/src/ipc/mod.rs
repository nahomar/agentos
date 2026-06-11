//! Inter-Process Communication — Channel-based messaging between agents.

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub sender_pid: u64,
    pub recipient: String,
    pub msg_type: String,
    pub content: String,
    pub timestamp: u64,
    pub msg_id: u64,
}

pub struct Broker {
    history: VecDeque<Message>,
    max_history: usize,
    msg_counter: u64,
}

impl Broker {
    pub fn new(max_history: usize) -> Self {
        Self {
            history: VecDeque::with_capacity(max_history),
            max_history,
            msg_counter: 0,
        }
    }

    pub fn publish(&mut self, mut msg: Message) -> u64 {
        self.msg_counter += 1;
        msg.msg_id = self.msg_counter;

        if self.history.len() >= self.max_history {
            self.history.pop_front();
        }
        self.history.push_back(msg);

        self.msg_counter
    }

    pub fn get_history(&self, limit: usize) -> Vec<&Message> {
        self.history.iter().rev().take(limit).collect()
    }

    pub fn stats(&self) -> BrokerStats {
        BrokerStats {
            messages_total: self.msg_counter,
            history_size: self.history.len(),
        }
    }
}

#[derive(Debug)]
pub struct BrokerStats {
    pub messages_total: u64,
    pub history_size: usize,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_publish_and_history() {
        let mut broker = Broker::new(5);
        for i in 0..10 {
            broker.publish(Message {
                sender_pid: 1,
                recipient: "all".into(),
                msg_type: "test".into(),
                content: format!("msg {}", i),
                timestamp: i,
                msg_id: 0,
            });
        }
        assert_eq!(broker.stats().messages_total, 10);
        assert_eq!(broker.stats().history_size, 5); // Only last 5 kept
    }
}
