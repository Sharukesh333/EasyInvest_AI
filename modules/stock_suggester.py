import random
from typing import List, Dict

# Import the offline price map from advisor module
try:
    from modules.advisor import OFFLINE_PRICES
except ImportError:
    OFFLINE_PRICES = {}

def _classify_risk(price: float) -> str:
    """Classify risk based on price thresholds.
    - High risk for penny stocks (< 100)
    - Medium risk for affordable (100-500)
    - Low risk for higher priced (> 500)
    """
    if price < 100:
        return "High"
    elif price <= 500:
        return "Medium"
    else:
        return "Low"

def suggest_stocks(budget: float, market: str = "NSE") -> List[Dict[str, any]]:
    """Suggest 2-3 different stocks from a predefined list within the given budget.
    The function runs synchronously and aims to return within ~2 seconds.

    Parameters:
        budget (float): Investment amount in INR.
        market (str): Market identifier (used for ticker suffix).

    Returns:
        List[Dict]: List of suggestion dictionaries with keys:
            - symbol
            - name
            - price
            - shares (max affordable within remaining budget)
            - total_cost
            - risk
    """
    suffix = ".NS" if market.upper() == "NSE" else ".BO"
    # Build candidate list from OFFLINE_PRICES
    candidates = []
    for name, price in OFFLINE_PRICES.items():
        if price <= 0:
            continue
        candidates.append({
            "symbol": f"{name}{suffix}",
            "name": name,
            "price": float(price),
            "risk": _classify_risk(float(price)),
        })
    # Filter by budget
    affordable = [c for c in candidates if c["price"] <= budget]
    if not affordable:
        return []
    # Group by risk for diversity
    risk_groups = {"Low": [], "Medium": [], "High": []}
    for c in affordable:
        risk_groups[c["risk"]].append(c)
    # Shuffle each group for randomness
    for group in risk_groups.values():
        random.shuffle(group)
    suggestions = []
    remaining = budget
    # Try to pick one from each risk level, highest to lowest budget impact
    for risk in ["Low", "Medium", "High"]:
        group = risk_groups[risk]
        for stock in group:
            if stock["price"] <= remaining:
                shares = int(remaining // stock["price"])
                if shares == 0:
                    continue
                total = round(shares * stock["price"], 2)
                suggestions.append({
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "price": stock["price"],
                    "shares": shares,
                    "total_cost": total,
                    "risk": stock["risk"],
                })
                remaining -= total
                break
        if len(suggestions) >= 3:
            break
    # If fewer than 2 suggestions, fill with cheapest remaining stocks
    if len(suggestions) < 2:
        sorted_affordable = sorted(affordable, key=lambda x: x["price"])
        for stock in sorted_affordable:
            if any(s["symbol"] == stock["symbol"] for s in suggestions):
                continue
            if stock["price"] <= remaining:
                shares = int(remaining // stock["price"])
                if shares == 0:
                    continue
                total = round(shares * stock["price"], 2)
                suggestions.append({
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "price": stock["price"],
                    "shares": shares,
                    "total_cost": total,
                    "risk": stock["risk"],
                })
                remaining -= total
                if len(suggestions) >= 3:
                    break
    return suggestions[:3]

# Example usage (can be removed in production)
if __name__ == "__main__":
    print(suggest_stocks(2000))
