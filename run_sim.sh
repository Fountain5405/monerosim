cargo build --release
target/release/monerosim --config test_configs/20260204_test.yaml
rm -rf shadow.data/
rm -rf shadow.log
nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
