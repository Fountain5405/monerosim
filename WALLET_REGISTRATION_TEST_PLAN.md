# Comprehensive Test Plan: Decentralized Wallet Registration

## Overview

This test plan validates the new decentralized wallet registration approach implemented in `block_controller.py` and `regular_user.py`. The approach replaces centralized wallet initialization with a decentralized mechanism where agents register their own wallet addresses in shared state files.

## Test Objectives

1. Verify that the block controller correctly waits for miner wallet registration
2. Test the `_wait_for_miner_wallet_registration()` method with various scenarios
3. Ensure the `_load_miner_registry()` method works with the new approach
4. Test error handling for delayed or missing miner registrations
5. Verify that both miners and regular users register their wallet addresses
6. Test the `_register_user_info()` and `_register_miner_info()` methods
7. Ensure wallet addresses are properly stored in the shared state
8. Test error handling and retry logic
9. Verify integration between components
10. Test timing scenarios and backward compatibility

## Test Scope

### Components Under Test
- `agents/block_controller.py` - Block controller agent
- `agents/regular_user.py` - Regular user agent
- Shared state file operations
- Agent discovery system integration

### Test Types
1. Unit Tests - Individual method testing
2. Integration Tests - Component interaction testing
3. Timing Tests - Fast/delayed registration scenarios
4. Error Handling Tests - Failure scenarios and recovery
5. Compatibility Tests - Backward compatibility verification

## Test Environment

### Test Files Structure
```
agents/
├── test_wallet_registration.py (existing)
├── test_block_controller_wallet_registration.py (new)
├── test_regular_user_wallet_registration.py (new)
├── test_integration_wallet_registration.py (new)
└── test_timing_scenarios.py (new)
```

### Test Data
- Mock miners.json file
- Mock agent_registry.json file
- Temporary shared state directory
- Mock wallet RPC responses

## Test Cases

### 1. Block Controller Tests

#### 1.1. `_wait_for_miner_wallet_registration()` Method Tests
- **TC-BC-001**: Normal flow - all miners register within expected time
- **TC-BC-002**: Slow registration - miners register at different times
- **TC-BC-003**: Missing miners.json file - error handling
- **TC-BC-004**: Corrupted miners.json file - error handling
- **TC-BC-005**: Timeout scenario - not all miners register within timeout
- **TC-BC-006**: Partial registration - some miners register, others don't
- **TC-BC-007**: Invalid miner info files - handling malformed JSON

#### 1.2. `_load_miner_registry()` Method Tests
- **TC-BC-008**: Normal flow - load miners with valid wallet addresses
- **TC-BC-009**: Fallback to agent registry when miner info files missing
- **TC-BC-010**: Handle missing wallet addresses in both sources
- **TC-BC-011**: Handle corrupted agent registry file
- **TC-BC-012**: Verify wallet address enrichment process

#### 1.3. `_update_agent_registry_with_miner_wallets()` Method Tests
- **TC-BC-013**: Normal flow - update registry with miner wallet addresses
- **TC-BC-014**: Handle missing agent registry file
- **TC-BC-015**: Handle corrupted agent registry file
- **TC-BC-016**: Verify atomic update operation

### 2. Regular User Tests

#### 2.1. `_register_miner_info()` Method Tests
- **TC-RU-001**: Normal flow - miner registers wallet address successfully
- **TC-RU-002**: Retry logic - handle temporary write failures
- **TC-RU-003**: No wallet address - skip registration gracefully
- **TC-RU-004**: Verify atomic file operations
- **TC-RU-005**: Verify exponential backoff in retry logic

#### 2.2. `_register_user_info()` Method Tests
- **TC-RU-006**: Normal flow - user registers wallet address successfully
- **TC-RU-007**: Retry logic - handle temporary write failures
- **TC-RU-008**: No wallet address - skip registration gracefully
- **TC-RU-009**: Verify atomic file operations
- **TC-RU-010**: Verify exponential backoff in retry logic

#### 2.3. Wallet Setup Tests
- **TC-RU-011**: Miner wallet setup - create/open wallet and register
- **TC-RU-012**: User wallet setup - create/open wallet and register
- **TC-RU-013**: Wallet creation failure handling
- **TC-RU-014**: Wallet opening failure handling

### 3. Integration Tests

#### 3.1. End-to-End Registration Flow
- **TC-IN-001**: Complete flow - miners register, block controller waits and finds addresses
- **TC-IN-002**: Multiple miners - verify all miners are registered and found
- **TC-IN-003**: Mixed agents - both miners and users register correctly
- **TC-IN-004**: Agent discovery integration - verify agent discovery can find registered agents

#### 3.2. Timing Scenarios
- **TC-TM-001**: Fast registration - all miners register immediately
- **TC-TM-002**: Staggered registration - miners register at different times
- **TC-TM-003**: Late registration - miners register just before timeout
- **TC-TM-004**: Very late registration - miners register after timeout

#### 3.3. Error Recovery Scenarios
- **TC-ER-001**: File system errors - handle permission issues
- **TC-ER-002**: Concurrent access - handle multiple agents writing simultaneously
- **TC-ER-003**: Network issues - handle RPC connection failures
- **TC-ER-004**: Resource exhaustion - handle out of memory/disk space

### 4. Backward Compatibility Tests

#### 4.1. Legacy Format Support
- **TC-BC-001**: Compatibility with old miners.json format
- **TC-BC-002**: Compatibility with old agent_registry.json format
- **TC-BC-003**: Mixed environment - new and old formats coexist

## Test Execution Plan

### Phase 1: Unit Tests
1. Implement block controller unit tests
2. Implement regular user unit tests
3. Execute tests and verify results

### Phase 2: Integration Tests
1. Create integration test suite
2. Test component interactions
3. Verify end-to-end functionality

### Phase 3: Timing and Error Tests
1. Implement timing scenario tests
2. Test error handling and recovery
3. Verify system resilience

### Phase 4: Compatibility Tests
1. Test backward compatibility
2. Verify migration scenarios
3. Document compatibility requirements

## Test Success Criteria

### Functional Criteria
- All miners successfully register wallet addresses
- Block controller correctly waits for and finds registered wallets
- Regular users successfully register wallet addresses
- Error scenarios are handled gracefully
- Retry logic works as expected

### Performance Criteria
- Registration completes within expected timeframes
- Memory usage remains within acceptable limits
- File operations are atomic and consistent
- System scales with number of agents

### Reliability Criteria
- No race conditions in concurrent access
- Proper cleanup of temporary files
- Robust error handling and recovery
- Consistent behavior across multiple runs

## Test Deliverables

1. Test scripts for all test cases
2. Test execution report
3. Performance metrics
4. Error handling validation
5. Compatibility assessment
6. Recommendations for improvements

## Timeline

- Phase 1: Unit Tests - 2 days
- Phase 2: Integration Tests - 1 day
- Phase 3: Timing and Error Tests - 1 day
- Phase 4: Compatibility Tests - 1 day
- Report Generation - 1 day

Total Estimated Duration: 6 days