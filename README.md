# ShitCode CLI

ShitCode Local Client Agent connects your local computer to AI assistants (ChatGPT, Claude Desktop, Cursor, and custom LLM agents) through an outbound-only WebSocket reverse tunnel.

Zero open ports, zero port forwarding, with native Windows (PowerShell) and Linux (Bash) execution.

## Quick Start

### Windows
```cmd
git clone https://github.com/snigdhkumar/shitcode-cli
cd shitcode-cli
shitcode.bat
```

### Linux
```bash
git clone https://github.com/snigdhkumar/shitcode-cli
cd shitcode-cli
chmod +x shitcode.sh
./shitcode.sh
```

## Setup & Authentication

1. Open your ShitCode Dashboard at [https://dashboard.shitcode.in](https://dashboard.shitcode.in)
2. Go to **Devices** and copy your permanent **Client Token** (`sc_client_...`)
3. On first run, paste your client token when prompted. It will be stored locally in `config.json`.
4. Choose your project workspace directory when prompted.

## CLI Commands

Inside the interactive terminal:
- `update [-y]`: Update client to the latest version via Git.
- `workspace <path>`: Switch project folder live without restarting.
- `perm`: Toggle between Auto-Approve and Interactive Approval.
- `status`: View live connection uptime, session ID, and ping.
- `tools`: List all 17 available tools and dynamic descriptions.
- `token`: View masked active device token.
- `reset`: Reset active device token and configure a new one.
- `clear`: Clear screen and re-render status banner.
- `help`: Show cheat sheet.
- `quit`: Safely disconnect and exit.

## Updating

To update ShitCode CLI to the latest release:

```bash
python shitcode.py update
```

To update directly without confirmation:
```bash
python shitcode.py update -y
```

Or run `update` or `update -y` inside the active CLI session.

> Note: Updating preserves your saved `config.json` and custom `skills/`.

## Architecture & Security

- **Outbound-only connection**: Client dials outward to `wss://api.shitcode.in/ws/client`. No listening ports are exposed on your network.
- **Interactive Approval Mode**: Option `--ask-permission` prompts for confirmation before modifying actions or shell commands execute.
- **Config Privacy**: `config.json` is strictly ignored by Git and never uploaded or shared.
