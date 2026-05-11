#!/usr/bin/env python3
"""
Phase 3 Main Entry Point

Run the Phase 3 World Engine with Digital Twin and OTA capabilities.

Usage:
    python main_phase3.py [--config CONFIG_FILE]
"""

import argparse
import asyncio
import logging
import signal
import sys

from world_engine.phase3.engine import Phase3WorldEngine, load_phase3_config
from world_engine.utils.config import setup_logging

logger = logging.getLogger(__name__)


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received")
    sys.exit(0)


async def main(config_file: str = "config.phase3.yaml"):
    """Main async function for Phase 3 engine."""
    # Setup logging
    setup_logging()
    
    # Load configuration
    config = load_phase3_config(config_file)
    logger.info(f"Loaded configuration from {config_file}")
    
    # Create Phase 3 engine
    engine = Phase3WorldEngine(config)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Run the engine
        await engine.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Engine error: {e}", exc_info=True)
    finally:
        # Cleanup
        await engine.shutdown()
        logger.info("Phase 3 engine stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 World Engine - Digital Twin & Secure Fleet")
    parser.add_argument(
        "--config",
        default="config.phase3.yaml",
        help="Path to configuration file (default: config.phase3.yaml)"
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.config))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
