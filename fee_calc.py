#!/usr/bin/env python3
"""Fee Calculation Automation Tool
Reads a trades CSV and computes incoming/outgoing fees, exports a summary Excel report.

Usage examples:
    python fee_calc.py --input trades_sample.csv --output report.xlsx --incoming-side Sell

"""
import argparse
import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def parse_args():
    p = argparse.ArgumentParser(description="Fee Calculation Automation Tool")
    p.add_argument("--input", "-i", type=str, required=True, help="Input trades CSV file")
    p.add_argument("--output", "-o", type=str, default="fee_report.xlsx", help="Output Excel report path")
    p.add_argument("--incoming-side", choices=["Sell","Buy"], default="Sell",
                   help="Which trade side is treated as incoming fees (default: Sell)")
    return p.parse_args()

def normalize_fee_rate(row):
    """Convert FeeRate into decimal fraction applied to Notional.
    FeeRateType can be: 'bps' (basis points), 'pct' (percent), or 'decimal' (already decimal fraction).
    """
    rate = row["FeeRate"]
    t = str(row.get("FeeRateType","")).lower()
    if t == "bps":
        return float(rate) / 10000.0   # 1 bps = 0.0001
    if t == "pct":
        return float(rate) / 100.0     # percent e.g., 0.1% -> 0.1/100
    # assume decimal
    return float(rate)

def compute_fees(df, incoming_side="Sell"):
    df = df.copy()
    df["fee_decimal"] = df.apply(normalize_fee_rate, axis=1)
    df["FeeAmount"] = df["Notional"].astype(float) * df["fee_decimal"]
    # classify incoming/outgoing based on side
    df["FeeDirection"] = df["Side"].apply(lambda s: "Incoming" if s == incoming_side else "Outgoing")
    return df

def generate_summary(df):
    total_incoming = df.loc[df["FeeDirection"]=="Incoming","FeeAmount"].sum()
    total_outgoing = df.loc[df["FeeDirection"]=="Outgoing","FeeAmount"].sum()
    summary = pd.DataFrame({
        "Metric":["Total Incoming Fees","Total Outgoing Fees","Net Fees (Incoming - Outgoing)"],
        "Amount":[total_incoming, total_outgoing, total_incoming - total_outgoing]
    })
    per_instrument = df.groupby("Instrument").agg(
        Trades=("TradeID","count"),
        TotalNotional=("Notional","sum"),
        TotalFees=("FeeAmount","sum")
    ).reset_index().sort_values("TotalFees", ascending=False)
    return summary, per_instrument

def main():
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        logging.error(f"Input file {input_path} does not exist.")
        return

    df = pd.read_csv(input_path, parse_dates=["TradeDate"])
    df_with_fees = compute_fees(df, incoming_side=args.incoming_side)
    summary, per_instrument = generate_summary(df_with_fees)

    out_path = Path(args.output)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_with_fees.to_excel(writer, sheet_name="trades_with_fees", index=False)
        summary.to_excel(writer, sheet_name="summary", index=False)
        per_instrument.to_excel(writer, sheet_name="by_instrument", index=False)
    logging.info(f"Report written to {out_path.resolve()}")

if __name__ == "__main__":
    main()
