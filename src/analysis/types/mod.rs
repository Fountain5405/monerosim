//! Core data types for transaction routing analysis.
//!
//! This module is split across several files grouped by analysis pipeline:
//!
//! - `core`: log primitives shared by every pipeline (`SimTime`, `Transaction`,
//!   `BlockInfo`, `AnalysisAgentInfo`, `ConnectionDirection`, `TxObservation`,
//!   `ConnectionEvent`, `BlockObservation`, `TxRelayProtocol`,
//!   `TxHashAnnouncement`, `TxRequest`, `ConnectionDrop`, `NodeLogData`).
//! - `spy`: spy-node analysis result types.
//! - `propagation`: propagation analysis result types.
//! - `resilience`: resilience analysis types and the top-level
//!   `FullAnalysisReport` / `AnalysisMetadata` aggregator.
//! - `tx_relay`: TX Relay V2 protocol analysis types.
//! - `dandelion`: Dandelion++ stem-path analysis types.
//! - `upgrade`: time-windowed types used by the upgrade-impact pipeline.
//! - `bandwidth`: bandwidth analysis types.
//!
//! All previously-public items are re-exported below so callers can keep
//! using `use crate::analysis::types::*;` (or the direct paths
//! `analysis::types::TypeName` from outside) unchanged.

mod bandwidth;
mod core;
mod dandelion;
mod propagation;
mod resilience;
mod spy;
mod tx_relay;
mod upgrade;

pub use bandwidth::{
    BandwidthEvent, BandwidthReport, BandwidthWindow, CategoryBandwidth, NodeBandwidthStats,
    PeerBandwidth,
};
pub use core::{
    AnalysisAgentInfo, BlockInfo, BlockObservation, ConnectionDirection, ConnectionDrop,
    ConnectionEvent, NodeLogData, SimTime, Transaction, TxHashAnnouncement, TxObservation,
    TxRelayProtocol, TxRequest,
};
pub use dandelion::{
    DandelionPath, DandelionPrivacyAssessment, DandelionReport, NodeDandelionStats, StemHop,
};
pub use propagation::{BottleneckNode, PropagationAnalysis, PropagationReport};
pub use resilience::{
    AnalysisMetadata, CentralizationMetrics, ConnectivityMetrics, FullAnalysisReport,
    PartitionRiskMetrics, ResilienceMetrics,
};
pub use spy::{
    FirstSeenEntry, SpyNodeReport, SpyNodeTxAnalysis, TimingDistribution, VulnerableSender,
};
pub use tx_relay::{
    ConnectionStabilityMetrics, ProtocolUsageStats, RequestResponseMetrics, TxDeliveryAnalysis,
    TxRelayAssessment, TxRelayV2Report,
};
pub use upgrade::{
    AggregatedMetrics, ChangeImpact, MetricChange, NodeUpgradeEvent, TimeWindow,
    UpgradeAnalysisMetadata, UpgradeAnalysisReport, UpgradeAssessment, UpgradeManifest,
    UpgradeVerdict, WindowedMetrics,
};
