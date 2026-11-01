#!/usr/bin/env python3
"""Add --sim-no-drop-score to the monero worktree (run on lithium; cwd = monero-knob).
A stock-rule node with this flag skips hit_score's height-drop penalty, as every
SoP node already does (mixed-adoption experiment, owner 2026-10-30)."""
import os
os.chdir(os.path.expanduser("~/.monerosim/build/monero-knob"))

def edit(path, pairs):
    s = open(path).read()
    for old, new in pairs:
        n = s.count(old)
        assert n == 1, f"{path}: anchor count {n} for {old[:70]!r}"
        s = s.replace(old, new)
    open(path, "w").write(s)
    print("edited", path)

if "m_sim_no_drop_score" not in open("src/cryptonote_protocol/cryptonote_protocol_handler.h").read():
  edit("src/cryptonote_protocol/cryptonote_protocol_handler.h", [(
"""    bool m_sync_pruned_blocks;
""",
"""    bool m_sync_pruned_blocks;
    bool m_sim_no_drop_score = false;   // SIMULATION ONLY: --sim-no-drop-score (mixed-adoption experiment)
""")])

edit("src/cryptonote_protocol/cryptonote_protocol_handler.inl", [(
"""  bool t_cryptonote_protocol_handler<t_core>::init(const boost::program_options::variables_map& vm)
  {
""",
"""  bool t_cryptonote_protocol_handler<t_core>::init(const boost::program_options::variables_map& vm)
  {
    // SIMULATION ONLY (2026-10-30): a stock-rule node that, like every SoP
    // node, does not score peers whose height drops (registered by core).
    m_sim_no_drop_score = vm.count("sim-no-drop-score") && vm["sim-no-drop-score"].as<bool>();
    if (m_sim_no_drop_score)
      MINFO("SIM: peer height drops not scored (--sim-no-drop-score)");
"""), (
"""    if (m_core.get_blockchain_storage().sim_sop_enabled())
    {
      MCLOG(el::Level::Info, "blockchain", el::Color::Default, context << "SIM-SoP: peer height drop not scored");
""",
"""    // --sim-no-drop-score (2026-10-30) gives a stock-rule node the same
    // exemption, so a mixed network can be run without stock nodes banning
    // their SoP peers for 24 h (sop_v4_adopt cells, 10-30).
    if (m_core.get_blockchain_storage().sim_sop_enabled() || m_sim_no_drop_score)
    {
      MCLOG(el::Level::Info, "blockchain", el::Color::Default, context << "SIM-SoP: peer height drop not scored");
""")])

edit("src/cryptonote_core/cryptonote_core.cpp", [(
"""  static const command_line::arg_descriptor<bool> arg_sim_sop_seen_at_notify = {
""",
"""  static const command_line::arg_descriptor<bool> arg_sim_no_drop_score = {
    "sim-no-drop-score"
  , "Simulation only: do not score (and eventually ban) peers whose chain height drops, as every Share-or-Perish node already does, on a node that keeps the stock fork rule; for mixed-adoption experiments (2026-10-30). Read by the protocol handler."
  , false
  };
  static const command_line::arg_descriptor<bool> arg_sim_sop_seen_at_notify = {
"""), (
"""  command_line::add_arg(desc, arg_sim_sop_seen_at_notify);
""",
"""  command_line::add_arg(desc, arg_sim_sop_seen_at_notify);
  command_line::add_arg(desc, arg_sim_no_drop_score);
""")])
print("all edits applied")
