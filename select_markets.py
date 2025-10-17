"""
Optimized Market Selection Script for Polymarket Bot

This script analyzes Volatility Markets and selects the top N markets
based on customizable criteria, then updates the Selected Markets sheet.
"""

import os
import sys
from dotenv import load_dotenv

# 重要: 在導入其他模組前先加載環境變數
load_dotenv()

import pandas as pd
from typing import Tuple, Optional
from poly_utils.google_utils import get_spreadsheet

# ============ Configuration ============
class MarketConfig:
    """Configuration for market selection criteria"""
    TOP_N = 5  # Number of markets to select
    
    # Filtering criteria
    MIN_REWARD = 1.0  # Minimum gm_reward_per_100
    MAX_VOLATILITY = 15  # Maximum volatility_sum
    MAX_SPREAD = 0.15  # Maximum spread
    MAX_MIN_SIZE = 300  # Maximum min_size
    
    # Scoring weights (for future enhancement)
    REWARD_WEIGHT = 1.0
    VOLATILITY_PENALTY = 1.0
    
    # Default values for new fields
    DEFAULT_PARAM_TYPE = 'mid'
    DEFAULT_MULTIPLIER = '1'

# ============ Helper Functions ============

def load_volatility_markets(spreadsheet) -> pd.DataFrame:
    """
    Load and clean Volatility Markets data from Google Sheets
    
    Returns:
        DataFrame with cleaned and typed data
    """
    try:
        vol_sheet = spreadsheet.worksheet('Volatility Markets')
        vol_df = pd.DataFrame(vol_sheet.get_all_records())
        
        # Remove empty rows
        vol_df = vol_df[vol_df['question'] != ''].reset_index(drop=True)
        
        # Ensure tokens are strings
        vol_df['token1'] = vol_df['token1'].astype(str)
        vol_df['token2'] = vol_df['token2'].astype(str)
        
        # Convert numeric columns
        numeric_cols = ['gm_reward_per_100', 'volatility_sum', 'best_bid', 
                       'best_ask', 'min_size', 'spread']
        for col in numeric_cols:
            if col in vol_df.columns:
                vol_df[col] = pd.to_numeric(vol_df[col], errors='coerce')
        
        print(f"✓ Loaded {len(vol_df)} markets from Volatility Markets sheet")
        return vol_df
        
    except Exception as e:
        print(f"✗ Error loading Volatility Markets: {e}")
        sys.exit(1)


def calculate_scores(df: pd.DataFrame, config: MarketConfig) -> pd.DataFrame:
    """
    Calculate selection scores for each market
    
    The score prioritizes high rewards and low volatility:
    score = (reward / (volatility + 1)) * 100
    """
    df = df.copy()
    df['score'] = (
        df['gm_reward_per_100'] / (df['volatility_sum'] + 1) * 100
    )
    return df


def filter_markets(df: pd.DataFrame, config: MarketConfig) -> pd.DataFrame:
    """
    Filter markets based on configured criteria
    
    Returns:
        Filtered and sorted DataFrame
    """
    filtered = df[
        (df['gm_reward_per_100'] >= config.MIN_REWARD) &
        (df['volatility_sum'] < config.MAX_VOLATILITY) &
        (df['spread'] < config.MAX_SPREAD) &
        (df['min_size'] <= config.MAX_MIN_SIZE)
    ].copy()
    
    # Sort by score (highest first)
    filtered = filtered.sort_values('score', ascending=False)
    
    print(f"✓ Filtered to {len(filtered)} markets meeting criteria")
    return filtered


def prepare_selected_markets(df: pd.DataFrame, config: MarketConfig) -> pd.DataFrame:
    """
    Prepare markets for insertion into Selected Markets sheet
    
    Adds required fields: max_size, trade_size, param_type, multiplier
    """
    df = df.copy()
    
    # Add required fields
    df['max_size'] = df['min_size'].astype(int).astype(str)
    df['trade_size'] = df['min_size'].astype(int).astype(str)
    df['param_type'] = config.DEFAULT_PARAM_TYPE
    df['multiplier'] = config.DEFAULT_MULTIPLIER
    
    return df


def print_market_summary(df: pd.DataFrame, title: str = "Selected Markets"):
    """
    Print a formatted summary of selected markets
    """
    print(f"\n{'=' * 80}")
    print(f"{title}")
    print('=' * 80)
    
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        # Truncate long questions
        question = row['question'][:70]
        if len(row['question']) > 70:
            question += "..."
            
        print(f"\n{idx}. {question}")
        print(f"   Reward: {row['gm_reward_per_100']:.2f} | "
              f"Volatility: {row['volatility_sum']:.2f} | "
              f"Spread: {row['spread']:.3f}")
        print(f"   Bid: {row['best_bid']:.2f} | "
              f"Ask: {row['best_ask']:.2f} | "
              f"Min Size: {row['min_size']:.0f}")
        print(f"   Score: {row['score']:.2f}")
    
    print('=' * 80)


def clear_selected_markets(sel_sheet) -> int:
    """
    Clear existing markets from Selected Markets sheet (keep header)
    
    Returns:
        Number of rows deleted
    """
    try:
        all_values = sel_sheet.get_all_values()
        rows_to_delete = len(all_values) - 1  # Exclude header
        
        if rows_to_delete > 0:
            sel_sheet.delete_rows(2, len(all_values))
            print(f"✓ Cleared {rows_to_delete} existing markets")
        else:
            print("✓ No existing markets to clear")
            
        return rows_to_delete
        
    except Exception as e:
        print(f"✗ Error clearing Selected Markets: {e}")
        return 0


def update_selected_markets(sel_sheet, markets_df: pd.DataFrame) -> bool:
    """
    Update Selected Markets sheet with new markets
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get headers from sheet
        headers = sel_sheet.row_values(1)
        
        # Add each market
        success_count = 0
        for _, row in markets_df.iterrows():
            # Map row values to headers
            row_values = [str(row.get(h, '')) for h in headers]
            sel_sheet.append_row(row_values, value_input_option='USER_ENTERED')
            success_count += 1
            
            # Print progress
            question = row['question'][:60]
            if len(row['question']) > 60:
                question += "..."
            print(f"  → Added: {question}")
        
        print(f"\n✓ Successfully added {success_count} markets to Selected Markets")
        return True
        
    except Exception as e:
        print(f"\n✗ Error updating Selected Markets: {e}")
        return False


# ============ Main Function ============

def main():
    """
    Main execution function
    
    1. Load Volatility Markets
    2. Calculate scores and filter
    3. Select top N markets
    4. Update Selected Markets sheet
    """
    config = MarketConfig()
    
    print("\n" + "=" * 80)
    print("POLYMARKET MARKET SELECTION")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  • Selecting top {config.TOP_N} markets")
    print(f"  • Min reward: {config.MIN_REWARD}")
    print(f"  • Max volatility: {config.MAX_VOLATILITY}")
    print(f"  • Max spread: {config.MAX_SPREAD}")
    print(f"  • Max min_size: {config.MAX_MIN_SIZE}")
    print()
    
    # 1. Load spreadsheet
    try:
        spreadsheet = get_spreadsheet()
        print("✓ Connected to Google Sheets")
    except Exception as e:
        print(f"✗ Failed to connect to Google Sheets: {e}")
        print(f"\n💡 Tip: Make sure .env file exists with SPREADSHEET_URL")
        sys.exit(1)
    
    # 2. Load and process Volatility Markets
    vol_df = load_volatility_markets(spreadsheet)
    
    # 3. Calculate scores
    vol_df = calculate_scores(vol_df, config)
    
    # 4. Filter markets
    filtered_df = filter_markets(vol_df, config)
    
    if len(filtered_df) == 0:
        print("\n✗ No markets meet the filtering criteria!")
        print("Consider relaxing the configuration parameters.")
        sys.exit(1)
    
    # 5. Select top N
    top_markets = filtered_df.head(config.TOP_N).copy()
    
    if len(top_markets) < config.TOP_N:
        print(f"\n⚠ Warning: Only {len(top_markets)} markets available "
              f"(requested {config.TOP_N})")
    
    # 6. Prepare markets for insertion
    top_markets = prepare_selected_markets(top_markets, config)
    
    # 7. Display summary
    print_market_summary(top_markets, f"Top {len(top_markets)} Markets")
    
    # 8. Update Selected Markets sheet
    print("\nUpdating Selected Markets sheet...")
    sel_sheet = spreadsheet.worksheet('Selected Markets')
    
    # Clear existing
    clear_selected_markets(sel_sheet)
    
    # Add new markets
    success = update_selected_markets(sel_sheet, top_markets)
    
    if success:
        print("\n" + "=" * 80)
        print("✓ MARKET SELECTION COMPLETE")
        print("=" * 80)
        print(f"\n{len(top_markets)} markets are now in Selected Markets.")
        print("The bot will begin trading these markets on the next update cycle.\n")
    else:
        print("\n✗ Failed to update Selected Markets")
        sys.exit(1)


if __name__ == "__main__":
    main()