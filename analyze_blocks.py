import json

# Read the blocks_found.json file
with open('shadow_agents_output/blocks_found.json', 'r') as f:
    blocks = json.load(f)

# Read the miners.json file
with open('/tmp/monerosim_shared/miners.json', 'r') as f:
    miners = json.load(f)

# Count blocks by miner
block_counts = {}
total_blocks = len(blocks)

for block in blocks:
    miner_id = block['miner_id']
    if miner_id in block_counts:
        block_counts[miner_id] += 1
    else:
        block_counts[miner_id] = 1

# Print results
print("Block Distribution Analysis")
print("============================")
print(f"Total blocks found: {total_blocks}")
print()

print("Blocks found by miner:")
for miner_id, count in block_counts.items():
    percentage = (count / total_blocks) * 100
    print(f"  {miner_id}: {count} blocks ({percentage:.1f}%)")

print()

print("Expected distribution from config:")
print("  user000: 50%")
print("  node000: 30%")
print("  node001: 20%")

print()

print("Actual distribution:")
for miner_id, count in block_counts.items():
    percentage = (count / total_blocks) * 100
    print(f"  {miner_id}: {percentage:.1f}%")