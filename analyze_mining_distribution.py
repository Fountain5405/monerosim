import json

# Read the blocks_found.json file
with open('/tmp/monerosim_shared/blocks_found.json', 'r') as f:
    blocks = json.load(f)

# Filter out blocks mined by non-mining agents
mining_blocks = [block for block in blocks if block['miner_id'] in ['user000', 'node000', 'node001']]

# Count blocks by miner
block_counts = {}
total_blocks = len(mining_blocks)

for block in mining_blocks:
    miner_id = block['miner_id']
    if miner_id in block_counts:
        block_counts[miner_id] += 1
    else:
        block_counts[miner_id] = 1

# Print results
print("Block Distribution Analysis")
print("============================")
print(f"Total mining blocks found: {total_blocks}")
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

print()
# Check if the distribution is close to expected
if total_blocks > 0:
    user000_percentage = (block_counts.get('user000', 0) / total_blocks) * 100
    node000_percentage = (block_counts.get('node000', 0) / total_blocks) * 100
    node001_percentage = (block_counts.get('node001', 0) / total_blocks) * 100
    
    print("Verification:")
    print(f"  user000: {user000_percentage:.1f}% (expected 50%) - {'PASS' if abs(user000_percentage - 50) < 10 else 'FAIL'}")
    print(f"  node000: {node000_percentage:.1f}% (expected 30%) - {'PASS' if abs(node000_percentage - 30) < 10 else 'FAIL'}")
    print(f"  node001: {node001_percentage:.1f}% (expected 20%) - {'PASS' if abs(node001_percentage - 20) < 10 else 'FAIL'}")
else:
    print("No mining blocks found!")