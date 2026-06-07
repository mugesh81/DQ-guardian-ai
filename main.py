"""DQ Guardian AI CLI and Entrypoint.

Supports running the Streamlit dashboard, FastAPI MCP server, or the offline agent loop.
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("dq_guardian_main")

# Load environment variables
load_dotenv()


def start_dashboard() -> NoReturn:
    """Launch the Streamlit dashboard on the configured port."""
    logger.info("Starting Streamlit Dashboard...")
    port = os.getenv("STREAMLIT_PORT", "8501")
    
    # Path to streamlit_app.py using pathlib
    dashboard_path = Path(__file__).parent / "app" / "dashboard" / "streamlit_app.py"
    
    if not dashboard_path.exists():
        logger.error(f"Streamlit application file not found at: {dashboard_path}")
        sys.exit(1)
        
    try:
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(dashboard_path),
            "--server.port",
            port,
        ]
        logger.info(f"Running command: {' '.join(cmd)}")
        # Use subprocess to run Streamlit
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        logger.info("Dashboard stopped by user.")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        logger.error(f"Streamlit failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        logger.exception(f"Unexpected error starting Streamlit dashboard: {e}")
        sys.exit(1)


def start_mcp_server() -> NoReturn:
    """Launch the FastAPI SSE MCP server on the configured port."""
    logger.info("Starting FastAPI MCP Server...")
    port = int(os.getenv("FASTAPI_PORT", "8000"))
    
    try:
        import uvicorn
        logger.info(f"Uvicorn serving app.mcp.server:app on port {port}")
        uvicorn.run("app.mcp.server:app", host="127.0.0.1", port=port, log_level="info")
    except ImportError:
        logger.error("Uvicorn or FastAPI not installed. Please run: pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error starting MCP server: {e}")
        sys.exit(1)


def run_agent_loop(data_path: Path, rules_path: Path) -> None:
    """Execute the offline agent loop.

    Args:
        data_path: Path to the dirty sales CSV.
        rules_path: Path to the YAML validation rules.
    """
    logger.info(f"Initializing Agent Loop with data: {data_path} and rules: {rules_path}")
    
    if not data_path.exists():
        logger.error(f"Data file does not exist: {data_path}")
        sys.exit(1)
        
    if not rules_path.exists():
        logger.error(f"Rules file does not exist: {rules_path}")
        sys.exit(1)
        
    try:
        # Import agent loop dynamically since it may not be created yet
        from app.agent.agent_loop import AgentLoop
        
        loop = AgentLoop(data_path=data_path, rules_path=rules_path)
        logger.info("Starting agent loop execution...")
        result = loop.run()
        logger.info("Agent loop execution completed.")
        print("\n=== AGENT LOOP RESULT ===")
        print(f"Status: {result.get('status', 'Unknown')}")
        print(f"Rules Evaluated: {result.get('rules_evaluated', 0)}")
        print(f"Rules Failed: {result.get('rules_failed', 0)}")
        print(f"Fixes Proposed: {len(result.get('proposed_fixes', []))}")
        print("==========================\n")
    except ImportError as e:
        logger.error(f"Failed to import Agent components. Make sure app/agent/agent_loop.py exists. Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Failed during agent loop execution: {e}")
        sys.exit(1)


def main() -> None:
    """Parse CLI arguments and run the specified mode."""
    parser = argparse.ArgumentParser(
        description="DQ Guardian AI - Data Quality Agentic Validator & Resolver"
    )
    
    parser.add_argument(
        "--mode",
        choices=["dashboard", "mcp", "agent"],
        required=True,
        help="Execution mode: 'dashboard' (Streamlit), 'mcp' (FastAPI MCP Server), or 'agent' (CLI Agent loop)",
    )
    
    # Arguments for agent mode
    parser.add_argument(
        "--data",
        type=str,
        help="Path to the dirty sales CSV file (required for agent mode)",
    )
    parser.add_argument(
        "--rules",
        type=str,
        help="Path to the validation rules YAML file (required for agent mode)",
    )
    
    args = parser.parse_args()
    
    if args.mode == "dashboard":
        start_dashboard()
    elif args.mode == "mcp":
        start_mcp_server()
    elif args.mode == "agent":
        if not args.data or not args.rules:
            parser.error("--data and --rules are required when --mode is 'agent'")
        run_agent_loop(Path(args.data), Path(args.rules))


if __name__ == "__main__":
    main()
