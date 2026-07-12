//! Shadow simulator configuration generation.
//!
//! Transforms Monerosim configs into Shadow YAML format (hosts, processes, network).

pub mod types;

pub use types::{
    AgentInfo, AgentRegistry, ExpectedFinalState, MinerInfo, MinerRegistry, ProcessArgs,
    PublicNodeInfo, PublicNodeRegistry, ShadowConfig, ShadowExperimental, ShadowFileSource,
    ShadowGeneral, ShadowGraph, ShadowHost, ShadowNetwork, ShadowNetworkEdge, ShadowNetworkNode,
    ShadowProcess,
};
