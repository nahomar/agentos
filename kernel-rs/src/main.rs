//! AgentOS Microkernel — Entry Point
//!
//! The kernel for agentic computing. Manages agent processes,
//! inter-process communication, capabilities, and the semantic bus.

mod ipc;
mod scheduler;
mod capability;
mod memory;
mod bus;
mod hal;

use scheduler::Scheduler;
use ipc::Broker;
use capability::CapabilityManager;

#[tokio::main]
async fn main() {
    println!("═══════════════════════════════════════════");
    println!("  AgentOS Kernel v0.1.0 \"genesis\"");
    println!("═══════════════════════════════════════════");
    println!();

    // Initialize kernel subsystems
    let scheduler = Scheduler::new(4); // max 4 concurrent
    let ipc_broker = Broker::new(1000); // 1000 message history
    let cap_manager = CapabilityManager::new();

    println!("  Scheduler:    initialized (max_concurrent=4)");
    println!("  IPC Broker:   initialized (history=1000)");
    println!("  Capabilities: initialized");
    println!("  Memory:       initialized");
    println!("  Semantic Bus: initialized");
    println!("  HAL:          detecting platform...");
    println!("  Platform:     {}", hal::detect_platform());
    println!();
    println!("  Kernel ready. Waiting for agents...");
}
