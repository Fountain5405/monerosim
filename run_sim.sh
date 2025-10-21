cargo build --release
target/release/monerosim --config config_47_agents.yaml 
rm -rf shadow.data/
rm -rf shadow.log 
nohup shadow shadow_output/shadow_agents.yaml > shadow.log 2>&1 &
