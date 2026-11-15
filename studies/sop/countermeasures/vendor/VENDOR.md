# Vendored: pto-selfish-mining

`blockchain_mdps/` is from <https://github.com/roibarzur/pto-selfish-mining>
at commit `89c408638c9c875457d596dcd30fe82114160422` (Zur, Eyal & Tamar 2020,
"Efficient MDP Analysis for Selfish-Mining in Blockchains"). MIT licence:
`LICENSE-pto-selfish-mining`.

Only `blockchain_mdps/base/` and `bitcoin_model.py` are copied. Changes:
- imports rewritten to work from this package (`from ... import
  BlockchainModel` became `from ..blockchain_model import BlockchainModel`;
  absolute `blockchain_mdps.base.` imports became
  `studies.sop.countermeasures.vendor.blockchain_mdps.base.`);
- `__init__.py` exports only the base classes, the solvers and
  `BitcoinModel`;
- `nx.from_numpy_matrix` and `nx.from_scipy_sparse_matrix` (removed in
  networkx 3) became `from_numpy_array` and `from_scipy_sparse_array`.

Nothing else changes; the study's own code is outside `vendor/`.
Dependencies: numpy, scipy, networkx, pymdptoolbox-roi (imported as
`mdptoolbox`), as in the lane-box venv `~/smcm/venv`.
