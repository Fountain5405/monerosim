# AI Config Generator

Generate monerosim configuration files from natural language descriptions.

## Quick Start

```bash
# Interactive mode
python3 -m scripts.ai_config

# Direct generation
python3 -m scripts.ai_config "5 miners and 50 users, 8 hour simulation"
```

## LLM Setup

The AI config generator requires an LLM provider. We recommend **Groq** (free tier, fast, good quality).

### Option 1: Groq (Recommended - Free)

1. **Sign up** at [console.groq.com](https://console.groq.com)
2. **Create an API key** in the Groq dashboard
3. **Configure**:

```bash
export OPENAI_API_KEY=gsk_your_groq_api_key_here
export OPENAI_BASE_URL=https://api.groq.com/openai/v1

python3 -m scripts.ai_config --model llama-3.3-70b-versatile
```

Or run interactively and enter these when prompted:
- API Base URL: `https://api.groq.com/openai/v1`
- API Key: `gsk_...` (your Groq key)
- Model: `llama-3.3-70b-versatile`

Settings are saved to `~/.monerosim/ai_config.yaml` for future use.

### Option 2: OpenAI (Paid, ~$0.001/config)

```bash
export OPENAI_API_KEY=sk-your_openai_key
export OPENAI_BASE_URL=https://api.openai.com/v1

python3 -m scripts.ai_config --model gpt-4o-mini
```

### Option 3: Local Model (llama.cpp)

Run a local llama.cpp server, then:

```bash
export OPENAI_API_KEY=not-needed
export OPENAI_BASE_URL=http://localhost:8080/v1

python3 -m scripts.ai_config --model your-model-name
```

**Note:** Local models smaller than 14B parameters may struggle with complex scenarios.

## Example Prompts

**Basic simulation:**
> "5 miners and 50 users running for 8 hours"

**Upgrade scenario:**
> "5 miners with hashrate 30,25,25,10,10. 20 users. At 7 hours, all nodes upgrade from monerod-v1 to monerod-v2. Run for 10 hours total."

**Spy node study:**
> "3 spy nodes with 100 in-peers and 100 out-peers monitoring a network of 5 miners and 30 users"

**Late-joining miners:**
> "5 miners at start (30,25,25,10,10 hashrate). 20 users at 30min. At 3 hours, 10 new miners join with hashrate 20 each using monerod-v2. 8 hours total."

## How It Works

1. **LLM generates Python script** - Creates code that builds the YAML config
2. **Script executes** - Produces YAML output
3. **Validator checks** - Ensures config is valid for monerosim
4. **Feedback loop** - If issues found, LLM corrects and retries (up to 3 attempts)

## CLI Options

```
python3 -m scripts.ai_config [OPTIONS] [REQUEST]

Options:
  -o, --output FILE      Output YAML file (default: generated_config.yaml)
  -s, --save-script FILE Save the Python generator script
  -m, --model MODEL      Override model name
  -u, --base-url URL     Override API base URL
  -a, --max-attempts N   Max correction attempts (default: 3)
  -q, --quiet            Suppress progress messages
  -v, --validate FILE    Validate existing config (no generation)
  --no-interactive       Disable interactive mode
```

## Validating Existing Configs

```bash
python3 -m scripts.ai_config --validate my_config.yaml
```

## Troubleshooting

**"Could not extract Python script from response"**
- The LLM didn't format code correctly
- Try a larger/smarter model (Groq's llama-3.3-70b-versatile works well)

**Timing errors (stop_time before upgrade starts)**
- The validator will catch this and prompt the LLM to fix it
- If it persists, simplify your prompt or specify exact times

**Hashrate validation errors**
- Initial miners (starting at t=0) must sum to 100 for difficulty calibration
- Late-joining miners can add extra hashrate

## Technical Details

- Uses OpenAI-compatible API format (works with Groq, OpenAI, local servers)
- Config stored in `~/.monerosim/ai_config.yaml`
- Prompts in `scripts/ai_config/prompts.py`
- Validation in `scripts/ai_config/validator.py`
