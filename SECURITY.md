# Security policy

## Supported versions

Monerosim is in 0.x public beta. Only the latest tagged minor line
receives security fixes — older 0.x.y tags will not be back-patched.

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |
| < 0.1   | ❌        |

When 0.2.0 ships, 0.1.x stops receiving fixes.

## Reporting a vulnerability

Please report security issues by email to **gingeropolous@gmail.com**.

Include:

- A description of the issue and the impact you believe it has.
- Steps to reproduce (a minimal config or test case is ideal).
- The version / commit hash you reproduced on.
- Whether the issue has been disclosed elsewhere.

**Do not** open a public GitHub issue for security reports — that
exposes the problem to anyone watching the repo before a fix is ready.

You should hear back within 7 days. If you don't, please follow up; the
inbox is monitored on a best-effort basis.

## Disclosure

This project follows coordinated disclosure. After a fix is ready and
released, the issue and fix are described in `CHANGELOG.md` with credit
to the reporter (with their permission). There is no bug bounty.

## What's in scope

Monerosim is a research and benchmarking tool that runs **inside**
Shadow's simulated network. The threat model is narrower than a
production cryptocurrency node:

- The tool launches `monerod` and `monero-wallet-rpc` processes inside
  Shadow, writes to `/tmp`, manages local RPC ports, and runs Python
  agents in the simulated process tree. Bugs that escape Shadow's
  sandbox to affect the host (file overwrites outside the project
  tree, RPC ports bound to externally-reachable interfaces, command
  injection from config files, etc.) are in scope.
- Bugs that allow arbitrary code execution from a malicious config
  file are in scope.
- Memory-safety issues in the Rust orchestrator that cause panics
  with attacker-controlled input are in scope as availability bugs.

## What's not in scope

- Vulnerabilities in upstream `monerod` / `monero-wallet-rpc` — please
  report those to the [Monero project](https://github.com/monero-project/monero/security)
  instead.
- Vulnerabilities in Shadow itself — report to the
  [Shadow project](https://github.com/shadow/shadow/security).
- Issues that only manifest on EL9 or other unsupported distros (see
  [PORTABILITY.md](PORTABILITY.md)).
- The unverified output of `tx-analyzer` — it is documented as
  exploratory and not a source of trustable analysis.
