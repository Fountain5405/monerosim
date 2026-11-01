#!/usr/bin/env python3
"""Apply the fluffy-arrival first-seen knob to the monero worktree (run on lithium, cwd =
~/.monerosim/build/monero-knob at commit "pop"). Every anchor must occur exactly once."""
import os, sys

def edit(path, pairs):
    s = open(path).read()
    for old, new in pairs:
        n = s.count(old)
        assert n == 1, f"{path}: anchor count {n} for {old[:60]!r}"
        s = s.replace(old, new)
    open(path, "w").write(s)
    print("edited", path)

os.chdir(os.path.expanduser("~/.monerosim/build/monero-knob"))

# 1. core: the flag, its registration and its wiring
edit("src/cryptonote_core/cryptonote_core.cpp", [
(
"""  // Lookup key only — the flag itself is registered by miner::init_options
  // ("sim-sop-w"); core reads the same variable_map without re-registering.
""",
"""  static const command_line::arg_descriptor<bool> arg_sim_sop_seen_at_notify = {
    "sim-sop-seen-at-notify"
  , "Simulation only: Share-or-Perish stamps a block's first-seen time when its P2P block notification (fluffy or full block) arrives, after the header parses and before any missing-transaction round trip, instead of when the full block qualifies in add_new_block (PoW passes, parent known). Default off (2026-10-30 knob)."
  , false
  };
  // Lookup key only — the flag itself is registered by miner::init_options
  // ("sim-sop-w"); core reads the same variable_map without re-registering.
"""),
(
"""  command_line::add_arg(desc, arg_sim_sop_rejudge_displaced);
""",
"""  command_line::add_arg(desc, arg_sim_sop_rejudge_displaced);
  command_line::add_arg(desc, arg_sim_sop_seen_at_notify);
"""),
(
"""          command_line::get_arg(vm, arg_sim_sop_rejudge_displaced));
""",
"""          command_line::get_arg(vm, arg_sim_sop_rejudge_displaced));
      m_blockchain_storage.set_sim_sop_seen_at_notify(command_line::get_arg(vm, arg_sim_sop_seen_at_notify));
      MINFO("SIM-SoP: first-seen stamped at " << (command_line::get_arg(vm, arg_sim_sop_seen_at_notify)
            ? "P2P notification (--sim-sop-seen-at-notify)" : "full-block qualification (default)"));
"""),
])

# 2. blockchain.h: setter, getter, hook, member
edit("src/cryptonote_core/blockchain.h", [
(
"""    bool sim_sop_enabled() const { return m_sim_sop_enabled; }
""",
"""    bool sim_sop_enabled() const { return m_sim_sop_enabled; }
    // SIMULATION ONLY (2026-10-30 knob): stamp a block's first-seen time at
    // its P2P notification (fluffy / full block), before any missing-tx
    // round trip, instead of when the full block qualifies in add_new_block.
    void set_sim_sop_seen_at_notify(bool on) { m_sim_sop_seen_at_notify = on; }
    bool sim_sop_seen_at_notify() const { return m_sim_sop_seen_at_notify; }
    void sim_sop_note_block_notify(const crypto::hash &id);
"""),
(
"""    bool m_sim_sop_rejudge = false;        // re-judge displaced blocks one at a time (implementation-hazard arm)
""",
"""    bool m_sim_sop_rejudge = false;        // re-judge displaced blocks one at a time (implementation-hazard arm)
    bool m_sim_sop_seen_at_notify = false; // first-seen stamped at the P2P notification (knob, default off)
"""),
])

# 3. blockchain.cpp: the hook, and add_new_block's drop-on-reject rule
edit("src/cryptonote_core/blockchain.cpp", [
(
"""        << (m_sim_sop_rejudge ? "rejudge" : "whole_branch") << ")");
}
""",
"""        << (m_sim_sop_rejudge ? "rejudge" : "whole_branch") << ")");
}

// SIMULATION ONLY (Share-or-Perish, 2026-10-30 knob): the protocol handler
// calls this when a block notification (fluffy or full block) arrives, after
// the header parses and before any missing-transaction round trip. With the
// knob on, the block's first-seen time is this moment; add_new_block's own
// stamp then finds the entry and keeps it (emplace). A block that later
// fails verification loses the stamp there; one that arrives before its
// parent keeps it (the header did show up). Without the knob: no-op.
void Blockchain::sim_sop_note_block_notify(const crypto::hash &id)
{
  if (!m_sim_sop_enabled || !m_sim_sop_seen_at_notify)
    return;
  CRITICAL_REGION_LOCAL(m_blockchain_lock);
  const uint64_t now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
      std::chrono::system_clock::now().time_since_epoch()).count();
  if (m_sim_recv.emplace(id, now_ms).second)
    MINFO("SIM-SoP: block " << id << " first seen at notify, t=" << now_ms);
}
"""),
(
"""  const bool sim_unseen_on_reject = sim_recorded && m_sim_sop_enabled;
""",
"""  const bool sim_unseen_on_reject = sim_recorded && m_sim_sop_enabled;
  // Knob (2026-10-30): a stamp set at the P2P notification (sim_recorded is
  // then false) survives an orphan verdict (the header did arrive) and is
  // dropped only if the block fails verification.
  const bool sim_unseen_on_invalid = !sim_recorded && m_sim_sop_enabled && m_sim_sop_seen_at_notify;
"""),
(
"""    if (sim_unseen_on_reject && (bvc.m_marked_as_orphaned || bvc.m_verifivation_failed))
      m_sim_recv.erase(id);
""",
"""    if ((sim_unseen_on_reject && (bvc.m_marked_as_orphaned || bvc.m_verifivation_failed))
        || (sim_unseen_on_invalid && bvc.m_verifivation_failed))
      m_sim_recv.erase(id);
"""),
(
"""  if (sim_unseen_on_reject && bvc.m_verifivation_failed)
    m_sim_recv.erase(id);
""",
"""  if ((sim_unseen_on_reject || sim_unseen_on_invalid) && bvc.m_verifivation_failed)
    m_sim_recv.erase(id);
"""),
])

# 4. protocol handler: the call site (NOTIFY_NEW_BLOCK is converted to fluffy and lands here too)
edit("src/cryptonote_protocol/cryptonote_protocol_handler.inl", [
(
"""    MLOG_P2P_MESSAGE(context << "Received NOTIFY_NEW_FLUFFY_BLOCK " << new_block_hash << " (height "
      << arg.current_blockchain_height << ", " << arg.b.txs.size() << " txes)");
""",
"""    MLOG_P2P_MESSAGE(context << "Received NOTIFY_NEW_FLUFFY_BLOCK " << new_block_hash << " (height "
      << arg.current_blockchain_height << ", " << arg.b.txs.size() << " txes)");

    // SIMULATION ONLY (Share-or-Perish, 2026-10-30 knob): first-seen at the
    // notification, before the missing-tx round trip (no-op unless armed).
    m_core.get_blockchain_storage().sim_sop_note_block_notify(new_block_hash);
"""),
])
print("all edits applied")
