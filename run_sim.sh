cargo build --release
#target/release/monerosim --config generated_config.yaml
target/release/monerosim --config test_configs/40_upgrade_scenario.yaml
#target/release/monerosim --config test_configs/multi_bin_test.yaml
rm -rf shadow.data/
rm -rf shadow.log 
nohup ~/.monerosim/bin/shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
