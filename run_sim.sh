cargo build --release
target/release/monerosim --config test_configs/20260112_config.yaml
#target/release/monerosim --config test_configs/multi_bin_test.yaml
rm -rf shadow.data/
rm -rf shadow.log 
nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
