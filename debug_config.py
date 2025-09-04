import yaml

# Load the configuration
with open('config_global_20_agents.yaml', 'r') as file:
    config = yaml.safe_load(file)

print("Loaded configuration successfully")
print(f"Number of user agents: {len(config['agents']['user_agents'])}")

# Check each user agent
for i, agent in enumerate(config['agents']['user_agents']):
    print(f"\nAgent {i}:")
    if 'attributes' in agent:
        print(f"  Attributes: {agent['attributes']}")
        if 'is_miner' in agent['attributes']:
            print(f"  is_miner attribute value: '{agent['attributes']['is_miner']}'")
            print(f"  is_miner type: {type(agent['attributes']['is_miner'])}")
        else:
            print("  No is_miner attribute found")
    else:
        print("  No attributes found")

    # Check if it should be a miner
    is_miner = False
    if 'attributes' in agent and 'is_miner' in agent['attributes']:
        is_miner_value = agent['attributes']['is_miner']
        if isinstance(is_miner_value, str):
            is_miner = is_miner_value.lower() in ['true', '1', 'yes', 'on']
        elif isinstance(is_miner_value, bool):
            is_miner = is_miner_value

    print(f"  Should be miner: {is_miner}")