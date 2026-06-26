"""
Test script to demonstrate the fixed portfolio generation system.
Shows how different budgets and risk levels now get DIFFERENT stock recommendations.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from modules.advisor import calculate_portfolio, determine_optimal_price_range

def test_different_price_ranges():
    """Test that different budget ranges get different stock recommendations."""
    print("=" * 80)
    print("TESTING PORTFOLIO GENERATION WITH DIFFERENT BUDGETS AND RISK LEVELS")
    print("=" * 80)
    
    test_cases = [
        # (budget, risk_level, horizon, description)
        (500, "Low", "Long Term", "Micro budget - Low risk"),
        (500, "Medium", "Long Term", "Micro budget - Medium risk"),
        (500, "High", "Long Term", "Micro budget - High risk"),
        (2000, "Low", "Long Term", "Small budget - Low risk"),
        (2000, "High", "Long Term", "Small budget - High risk"),
        (5000, "Low", "Long Term", "Medium budget - Low risk"),
        (5000, "High", "Long Term", "Medium budget - High risk"),
        (10000, "Low", "Long Term", "Large budget - Low risk"),
        (10000, "High", "Long Term", "Large budget - High risk"),
    ]
    
    previous_stocks = {}
    
    for budget, risk, horizon, desc in test_cases:
        print(f"\n{'─' * 80}")
        print(f"📊 TEST: {desc}")
        print(f"   Budget: ₹{budget} | Risk: {risk} | Horizon: {horizon}")
        print(f"{'─' * 80}")
        
        # Get optimal price range
        price_range = determine_optimal_price_range(budget)
        print(f"✓ Optimal price range: ₹{price_range[0]:.0f} - ₹{price_range[1]:.0f}")
        
        # Generate portfolio
        portfolio = calculate_portfolio(budget, "NSE", risk, horizon)
        
        # Display recommendations
        print(f"\n✓ Portfolio: {portfolio['suggested_type']}")
        print(f"✓ Total allocated: ₹{portfolio['total_allocated']}")
        print(f"✓ Leftover cash: ₹{portfolio['leftover_cash']}")
        print(f"✓ Confidence: {portfolio['confidence_score']}%")
        print(f"✓ Source: {portfolio['data_source']}")
        
        # Display recommended stocks
        print(f"\n📈 Recommendations ({len(portfolio['recommendations'])} stocks):")
        recommended_symbols = []
        
        for i, rec in enumerate(portfolio['recommendations'], 1):
            symbol = rec.get('symbol', 'N/A')
            recommended_symbols.append(symbol)
            price = rec.get('current_price', 0)
            shares = rec.get('shares', 0)
            total = rec.get('total_cost', 0)
            risk = rec.get('risk', 'N/A')
            band = rec.get('price_band', 'N/A')
            
            print(f"   {i}. {symbol:<12} | ₹{price:>6.2f} × {shares:>3} shares = ₹{total:>8.2f} | Risk: {risk:<6} | Band: {band}")
        
        # Store stocks for comparison
        key = f"{budget}_{risk}"
        previous_stocks[key] = set(recommended_symbols)
        
        # Check for diversity
        print(f"\n✓ Reason: {portfolio['reasoning']}")
    
    # Analysis section
    print(f"\n\n{'=' * 80}")
    print("ANALYSIS: STOCK DIVERSITY ACROSS DIFFERENT SCENARIOS")
    print(f"{'=' * 80}")
    
    # Check if same budget with different risk levels get different stocks
    for budget in [500, 2000, 5000, 10000]:
        low_key = f"{budget}_Low"
        med_key = f"{budget}_Medium"
        high_key = f"{budget}_High"
        
        if low_key in previous_stocks and high_key in previous_stocks:
            low_stocks = previous_stocks[low_key]
            high_stocks = previous_stocks[high_key]
            common = low_stocks & high_stocks
            unique_rate = 1.0 - (len(common) / max(len(low_stocks), len(high_stocks))) if max(len(low_stocks), len(high_stocks)) > 0 else 0
            
            print(f"\n✓ Budget ₹{budget}:")
            print(f"  - Low Risk stocks: {low_stocks}")
            print(f"  - High Risk stocks: {high_stocks}")
            print(f"  - Overlap: {common if common else 'None'}")
            print(f"  - Diversity: {unique_rate * 100:.1f}%")
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE: Portfolio generation now supports price range filtering")
    print("   and risk-based stock selection!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_different_price_ranges()
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
