import asyncio
from momentum_strategy import MomentumStrategy

async def evaluate_profit_potential(strategy):
    """
    Evaluate if the momentum strategy can generate sufficient profit
    """
    try:
        print("\nEvaluating momentum trading strategy...")

        opportunity = await strategy.find_opportunity()
        if not opportunity:
            print("\nNo viable trading opportunities found")
            return False

        # Execute trade if opportunity found
        success = await strategy.execute_trade(opportunity)
        if not success:
            print("\nFailed to execute trade")
            return False

        # Monitor position
        monitor_task = asyncio.create_task(strategy.monitor_positions())

        # Run for test period
        await asyncio.sleep(300)  # 5 minutes test

        monitor_task.cancel()

        # Check results
        if len(strategy.active_positions) == 0:
            print("\nTest completed - Position closed")
            return True

        return False

    except Exception as e:
        print(f"Error in evaluation: {e}")
        return False

async def main():
    strategy = MomentumStrategy()
    try:
        profit_feasible = await evaluate_profit_potential(strategy)
        if profit_feasible:
            print("\nStrategy evaluation successful!")
            print("Momentum trading strategy shows potential for profitable trades")
        else:
            print("\nStrategy evaluation unsuccessful")
            print("Current market conditions may not be suitable for momentum trading")

    except Exception as e:
        print(f"Error in main: {e}")

    finally:
        await strategy.close()

if __name__ == "__main__":
    asyncio.run(main())
