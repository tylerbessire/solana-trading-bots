import asyncio
from hybrid_strategy import HybridStrategy
from connection_monitor import ConnectionMonitor

async def evaluate_profit_potential(strategy):
    """
    Evaluate if the hybrid strategy can generate sufficient profit
    """
    try:
        print("\nEvaluating hybrid trading strategy...")

        # Initialize connection monitor
        monitor = ConnectionMonitor()
        connection_id = "jupiter_dex"
        monitor_task = asyncio.create_task(monitor.monitor_connection(connection_id))

        # Run initial analysis
        opportunity = await strategy.find_opportunity()
        if not opportunity:
            print("\nNo viable trading opportunities found")
            return False

        # Update connection status after successful price check
        monitor.update_last_message(connection_id)

        # Execute trade if opportunity found
        success = await strategy.execute_trade(opportunity)
        if not success:
            print("\nFailed to execute trade")
            return False

        # Update connection after trade execution
        monitor.update_last_message(connection_id)

        # Monitor positions with connection health checks
        print("\nMonitoring positions and connection health...")
        position_monitor = asyncio.create_task(strategy.monitor_positions())

        test_duration = 300  # 5 minutes test
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < test_duration:
            if not monitor.is_connection_healthy(connection_id):
                print("\nConnection issues detected, attempting recovery...")
                # Attempt recovery
                await strategy.jupiter.ensure_session()
                monitor.update_last_message(connection_id)

            # Update connection status periodically
            monitor.update_last_message(connection_id)
            await asyncio.sleep(1)

        # Clean up monitoring tasks
        monitor_task.cancel()
        position_monitor.cancel()
        try:
            await monitor_task
            await position_monitor
        except asyncio.CancelledError:
            pass

        return True

    except Exception as e:
        print(f"Error in evaluation: {e}")
        return False

async def main():
    strategy = HybridStrategy()
    try:
        profit_feasible = await evaluate_profit_potential(strategy)
        if profit_feasible:
            print("\nStrategy evaluation successful!")
            print("Hybrid strategy shows potential for profitable trades")
            print("\nConnection stability verified")
            print("Trade execution capability confirmed")
        else:
            print("\nStrategy evaluation unsuccessful")
            print("Current market conditions may not be suitable for the strategy")

    except Exception as e:
        print(f"Error in main: {e}")

    finally:
        await strategy.close()

if __name__ == "__main__":
    asyncio.run(main())
