//! Shadow simulator configuration generation.
//!
//! Transforms Monerosim configs into Shadow YAML format (hosts, processes, network).

pub mod types;

pub use types::{
    MinerInfo,
    MinerRegistry,
    AgentInfo,
    AgentRegistry,
    PublicNodeInfo,
    PublicNodeRegistry,
    ShadowConfig,
    ShadowGeneral,
    ShadowExperimental,
    ShadowNetwork,
    ShadowGraph,
    ShadowFileSource,
    ShadowNetworkNode,
    ShadowNetworkEdge,
    ShadowHost,
    ShadowProcess,
    ExpectedFinalState,
};
