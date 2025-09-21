import asyncio
import json
from dotenv import load_dotenv
import time
from market_maker import MarketMaker
from strategy import TradingStrategy
from executor import TradeExecutor

async def test_websocket_stability(market_maker):
    """Test WebSocket connection stability"""
    print("Starting WebSocket stability test (60 seconds)...")
    test_duration = 60  # 1 minute test
    disconnections = 0
    start_time = time.time()
    last_status = True  # Track last connection status

    while time.time() - start_time < test_duration:
        current_status = market_maker.ws and not market_maker.ws.closed
        if last_status and not current_status:
            disconnections += 1
            print(f"WebSocket disconnection detected (total: {disconnections})")
        last_status = current_status
        await asyncio.sleep(1)

    print(f"WebSocket stability test completed: {disconnections} disconnections in {test_duration} seconds")
    return disconnections == 0

async def test_transaction_execution(executor, strategy):
    """Test transaction execution with simulated opportunity"""
    print("Testing transaction execution with simulated opportunity...")

    # Simulate a small test trade (0.01 SOL)
    test_amount = 0.01
    test_token_address = "So11111111111111111111111111111111111111112"  # SOL token address
    test_target_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC token address

    try:
        # Create simulated opportunity
        opportunity = {
            'input_token': test_token_address,
            'output_token': test_target_token,
            'amount': test_amount,
            'expected_output': test_amount * 20,  # Simulated USDC output (1 SOL ≈ 20 USDC)
            'route': 'jupiter_v6'
        }

        # Attempt test trade
        success = await executor.execute_trade(opportunity)
        if success:
            print("Successfully executed test trade")
            return True
        else:
            print("Failed to execute test trade")
            return False

    except Exception as e:
        print(f"Error in transaction execution test: {e}")
        return False

async def evaluate_profit_potential(strategy, duration_seconds=300):
    """Evaluate profit potential over test duration"""
    print(f"Evaluating profit potential over {duration_seconds} seconds...")
    print("Scanning for trading opportunities...")

    start_time = time.time()
    opportunities_found = 0
    total_potential_profit = 0
    last_update_time = start_time
    update_interval = 30  # Progress update every 30 seconds

    try:
        while time.time() - start_time < duration_seconds:
            # Look for trading opportunities
            opportunity = await strategy.find_opportunity()

            # Show progress update periodically
            current_time = time.time()
            if current_time - last_update_time >= update_interval:
                elapsed = int(current_time - start_time)
                remaining = duration_seconds - elapsed
                print(f"Progress: {elapsed}s elapsed, {remaining}s remaining")
                print(f"Opportunities found so far: {opportunities_found}")
                print(f"Total potential profit so far: ${total_potential_profit:.2f}\n")
                last_update_time = current_time

            if opportunity:
                opportunities_found += 1
                potential_profit = opportunity.get('expected_profit', 0)
                total_potential_profit += potential_profit
                print(f"Found opportunity #{opportunities_found} - Potential profit: ${potential_profit:.2f}")

            # Small delay to prevent overwhelming the API
            await asyncio.sleep(1)

        # Calculate metrics
        test_duration_hours = duration_seconds / 3600
        opportunities_per_hour = opportunities_found / test_duration_hours
        avg_profit_per_opportunity = total_potential_profit / opportunities_found if opportunities_found > 0 else 0
        estimated_daily_profit = opportunities_per_hour * 24 * avg_profit_per_opportunity

        print("\nProfit Potential Analysis:")
        print(f"Test duration: {duration_seconds} seconds ({test_duration_hours:.2f} hours)")
        print(f"Total opportunities found: {opportunities_found}")
        print(f"Average profit per opportunity: ${avg_profit_per_opportunity:.2f}")
        print(f"Estimated opportunities per hour: {opportunities_per_hour:.1f}")
        print(f"Estimated daily profit potential: ${estimated_daily_profit:.2f}")

        # Determine if $1000 profit goal is feasible
        is_feasible = estimated_daily_profit >= 1000
        print(f"\nProfit goal of $1000/day is {'feasible' if is_feasible else 'not feasible'} "
              f"with current market conditions")
        if not is_feasible:
            print(f"Need ${1000 - estimated_daily_profit:.2f} more in daily profit to reach goal")

        return is_feasible

    except Exception as e:
        print(f"Error in profit potential evaluation: {e}")
        return False

async def main():
    load_dotenv()

    # Initialize components
    market_maker = MarketMaker()
    strategy = TradingStrategy()
    executor = TradeExecutor()

    try:
        print("Starting strategy evaluation...")

        # Initialize market maker
        await market_maker.start()
        await asyncio.sleep(2)  # Allow WebSocket connection to establish

        # Test 1: WebSocket Stability
        print("\nTesting WebSocket stability...")
        ws_stable = await test_websocket_stability(market_maker)
        if not ws_stable:
            print("WARNING: WebSocket connection unstable")
        else:
            print("WebSocket stability test passed")

        # Test 2: Transaction Execution
        print("\nTesting transaction execution...")
        tx_success = await test_transaction_execution(executor, strategy)
        if not tx_success:
            print("WARNING: Transaction execution test failed")
        else:
            print("Transaction execution test passed")

        # Test 3: Profit Potential
        print("\nEvaluating profit potential...")
        profit_feasible = await evaluate_profit_potential(strategy)

        # Final evaluation
        print("\nFinal Evaluation Results:")
        print(f"WebSocket Stability: {'PASS' if ws_stable else 'FAIL'}")
        print(f"Transaction Execution: {'PASS' if tx_success else 'FAIL'}")
        print(f"Profit Target Feasible: {'YES' if profit_feasible else 'NO'}")

        if ws_stable and tx_success and profit_feasible:
            print("\nStrategy evaluation PASSED - Ready for production deployment")
        else:
            print("\nStrategy evaluation FAILED - Needs improvements")

    except Exception as e:
        print(f"Error in evaluation: {e}")
    finally:
        # Cleanup
        await market_maker.close()
        await strategy.close()
        await executor.close()

if __name__ == "__main__":
    asyncio.run(main())
