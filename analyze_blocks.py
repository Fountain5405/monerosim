import json

# Read the blocks_found.json file
with open('/tmp/monerosim_shared/blocks_found.json', 'r') as f:
    blocks = json.load(f)

# Read the miners.json file
with open('/tmp/monerosim_shared/miners.json', 'r') as f:
    miners = json.load(f)

# Count blocks by miner
block_counts = {}
total_blocks = len(blocks)

for block in blocks:
    miner_ip = block['miner_ip']
    if miner_ip in block_counts:
        block_counts[miner_ip] += 1
    else:
        block_counts[miner_ip] = 1

# Print results
print("Block Distribution Analysis")
print("============================")
print(f"Total blocks found: {total_blocks}")
print()

print("Blocks found by miner:")
for miner_ip, count in block_counts.items():
    percentage = (count / total_blocks) * 100
    print(f"  {miner_ip}: {count} blocks ({percentage:.1f}%)")

print()

print("Expected distribution from config:")
print("  10.0.0.34 (user000): 25%")
print("  10.0.0.35 (user001): 25%")
print("  10.0.0.36 (user002): 20%")
print("  10.0.0.37 (user003): 15%")
print("  10.0.0.38 (user004): 15%")

print()

print("Actual distribution:")
for miner_ip, count in block_counts.items():
    percentage = (count / total_blocks) * 100
    print(f"  {miner_ip}: {percentage:.1f}%")