import argparse
import datetime as dt
import json
import os
import sys

import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a Markdown report from a JSONL experiment log."
    )
    parser.add_argument("--log", required=True, help="Path to JSONL log file")
    parser.add_argument("--output-dir", default="reports", help="Output directory")
    parser.add_argument(
        "--output-name",
        default=None,
        help="Output filename (default: {stem}_{timestamp}.md)",
    )
    parser.add_argument(
        "--method-field", default="method", help="JSON key for method name"
    )
    parser.add_argument(
        "--metric-field", default="value", help="JSON key for primary metric"
    )
    parser.add_argument(
        "--runtime-field", default="runtime", help="JSON key for runtime"
    )
    parser.add_argument(
        "--group-field", default="dataset", help="JSON key for grouping"
    )
    parser.add_argument(
        "--filter",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Filter records (repeatable), e.g. --filter ver=taskA-v2",
    )
    parser.add_argument(
        "--lower-is-better",
        action="store_true",
        default=False,
        help="Reverse ranking direction (lower metric is better)",
    )
    parser.add_argument("--title", default="Experiment Report", help="Report title")
    parser.add_argument("--overview", default=None, help="Override overview paragraph")
    parser.add_argument(
        "--findings",
        default=None,
        help="Override findings (semicolon-separated)",
    )
    parser.add_argument(
        "--conclusions",
        default=None,
        help="Override conclusions (semicolon-separated)",
    )
    return parser.parse_args()


def load_records(log_path, filters):
    records = []
    with open(log_path, "r") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                records.append(obj)
            except json.JSONDecodeError as e:
                print(
                    f"Warning: skipping malformed JSON on line {lineno}: {e}",
                    file=sys.stderr,
                )

    df = pd.DataFrame(records)

    for filt in filters:
        if "=" not in filt:
            print(
                f"Warning: ignoring malformed filter (expected KEY=VALUE): {filt}",
                file=sys.stderr,
            )
            continue
        key, value = filt.split("=", 1)
        if key in df.columns:
            df = df[df[key].astype(str) == value]
        else:
            print(
                f"Warning: filter key '{key}' not found in data, ignoring.",
                file=sys.stderr,
            )

    return df


def compute_summary(df, method_field, metric_field, group_field):
    summary = {
        "total_records": len(df),
        "methods": (
            sorted(df[method_field].dropna().unique().tolist())
            if method_field in df.columns
            else []
        ),
        "groups": (
            sorted(df[group_field].dropna().unique().tolist())
            if group_field in df.columns
            else []
        ),
        "seeds": (
            sorted(df["seed"].dropna().unique().tolist())
            if "seed" in df.columns
            else []
        ),
        "reps": (
            sorted(df["rep"].dropna().unique().tolist()) if "rep" in df.columns else []
        ),
        "metric_min": df[metric_field].min() if metric_field in df.columns else None,
        "metric_max": df[metric_field].max() if metric_field in df.columns else None,
        "method_field": method_field,
        "metric_field": metric_field,
        "group_field": group_field,
    }
    return summary


def compute_method_ranking(
    df, method_field, metric_field, runtime_field, lower_is_better
):
    has_runtime = runtime_field in df.columns and df[runtime_field].notna().any()

    agg = {metric_field: ["mean", "std", "count"]}
    if has_runtime:
        agg[runtime_field] = "mean"

    grouped = df.groupby(method_field).agg(agg)
    grouped.columns = ["mean_metric", "std_metric", "count"] + (
        ["mean_runtime"] if has_runtime else []
    )
    grouped = grouped.reset_index()

    grouped = grouped.sort_values("mean_metric", ascending=lower_is_better).reset_index(
        drop=True
    )
    grouped.insert(0, "rank", range(1, len(grouped) + 1))

    best_val = grouped["mean_metric"].iloc[0]
    if lower_is_better:
        grouped["gap_to_best"] = grouped["mean_metric"] - best_val
    else:
        grouped["gap_to_best"] = best_val - grouped["mean_metric"]

    grouped["has_runtime"] = has_runtime
    return grouped


def compute_cross_table(df, method_field, metric_field, group_field):
    if group_field not in df.columns or method_field not in df.columns:
        return None
    if df[group_field].nunique() < 2 or df[method_field].nunique() < 1:
        return None
    cross = pd.pivot_table(
        df,
        values=metric_field,
        index=group_field,
        columns=method_field,
        aggfunc="mean",
    )
    return cross


def generate_narrative(summary, ranking_df, cross_df, lower_is_better):
    metric = summary["metric_field"]
    group = summary["group_field"]
    n_methods = len(summary["methods"])
    n_groups = len(summary["groups"])

    # Overview
    direction = "lower" if lower_is_better else "higher"
    overview = (
        f"This report summarises {summary['total_records']} experiment records across "
        f"{n_methods} method(s) and {n_groups} {group}(s). "
        f"The primary metric is `{metric}` ({direction} is better). "
    )
    if summary["seeds"]:
        overview += f"Seeds used: {summary['seeds']}. "
    if summary["reps"]:
        overview += f"Repetitions: {summary['reps']}. "
    if summary["metric_min"] is not None:
        overview += f"Metric ranges from {summary['metric_min']:.4f} to {summary['metric_max']:.4f}."

    # Findings
    findings = []
    if len(ranking_df) > 0:
        best = ranking_df.iloc[0]
        findings.append(
            f"Best method: **{best[summary['method_field']]}** with mean {metric} = {best['mean_metric']:.4f}."
        )
    if len(ranking_df) > 1:
        worst = ranking_df.iloc[-1]
        findings.append(
            f"Worst method: **{worst[summary['method_field']]}** with mean {metric} = {worst['mean_metric']:.4f}."
        )
        spread = abs(ranking_df["mean_metric"].max() - ranking_df["mean_metric"].min())
        findings.append(f"Spread between best and worst: {spread:.4f}.")

    has_runtime = ranking_df["has_runtime"].iloc[0] if len(ranking_df) > 0 else False
    if has_runtime and "mean_runtime" in ranking_df.columns:
        fastest = ranking_df.loc[ranking_df["mean_runtime"].idxmin()]
        findings.append(
            f"Fastest method: **{fastest[summary['method_field']]}** "
            f"with mean runtime {fastest['mean_runtime']:.6f}s."
        )

    if cross_df is not None and n_groups > 1:
        findings.append(
            f"Cross-{group} performance is shown in Section 4; "
            "see the pivot table for per-group breakdown."
        )

    # Conclusions
    conclusions = []
    if len(ranking_df) > 0:
        best = ranking_df.iloc[0]
        conclusions.append(
            f"**{best[summary['method_field']]}** is the recommended method "
            f"based on mean {metric}."
        )
    if len(ranking_df) > 1:
        conclusions.append(
            "Consider further experiments with more seeds or datasets to confirm these rankings."
        )
    else:
        conclusions.append(
            "Only one method evaluated; no comparative conclusions can be drawn."
        )

    return overview, findings, conclusions


def format_markdown(
    title, timestamp, overview, findings, conclusions, summary, ranking_df, cross_df
):
    method_field = summary["method_field"]
    metric_field = summary["metric_field"]
    group_field = summary["group_field"]
    has_runtime = ranking_df["has_runtime"].iloc[0] if len(ranking_df) > 0 else False

    lines = []

    # Title + timestamp
    lines.append(f"# {title}")
    lines.append(f"*Generated: {timestamp}*")
    lines.append("")

    # Section 1: Overview
    lines.append("## 1. Experiment Overview")
    lines.append("")
    lines.append(overview)
    lines.append("")
    lines.append("| Statistic | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total records | {summary['total_records']} |")
    lines.append(
        f"| Methods | {len(summary['methods'])} ({', '.join(str(m) for m in summary['methods'])}) |"
    )
    lines.append(
        f"| {group_field.capitalize()}s | {len(summary['groups'])} ({', '.join(str(g) for g in summary['groups'])}) |"
    )
    if summary["seeds"]:
        lines.append(f"| Seeds | {', '.join(str(s) for s in summary['seeds'])} |")
    if summary["reps"]:
        lines.append(f"| Repetitions | {', '.join(str(r) for r in summary['reps'])} |")
    if summary["metric_min"] is not None:
        lines.append(
            f"| {metric_field} range | [{summary['metric_min']:.4f}, {summary['metric_max']:.4f}] |"
        )
    lines.append("")

    # Section 2: Key Findings
    lines.append("## 2. Key Findings")
    lines.append("")
    for i, f in enumerate(findings, 1):
        lines.append(f"{i}. {f}")
    lines.append("")

    # Section 3: Method Ranking
    lines.append("## 3. Method Ranking")
    lines.append("")
    if has_runtime and "mean_runtime" in ranking_df.columns:
        header = f"| Rank | Method | Mean {metric_field} | Std | Mean Runtime (s) | Count | Gap to Best |"
        sep = "|---|---|---|---|---|---|---|"
    else:
        header = f"| Rank | Method | Mean {metric_field} | Std | Count | Gap to Best |"
        sep = "|---|---|---|---|---|---|"
    lines.append(header)
    lines.append(sep)
    for _, row in ranking_df.iterrows():
        std_val = f"{row['std_metric']:.4f}" if pd.notna(row["std_metric"]) else "N/A"
        if has_runtime and "mean_runtime" in ranking_df.columns:
            rt_val = (
                f"{row['mean_runtime']:.6f}" if pd.notna(row["mean_runtime"]) else "N/A"
            )
            lines.append(
                f"| {int(row['rank'])} | {row[method_field]} | {row['mean_metric']:.4f} "
                f"| {std_val} | {rt_val} | {int(row['count'])} | {row['gap_to_best']:.4f} |"
            )
        else:
            lines.append(
                f"| {int(row['rank'])} | {row[method_field]} | {row['mean_metric']:.4f} "
                f"| {std_val} | {int(row['count'])} | {row['gap_to_best']:.4f} |"
            )
    lines.append("")

    # Section 4: Cross-table
    lines.append(f"## 4. {group_field.capitalize()} x Method Cross-Table")
    lines.append("")
    if cross_df is not None:
        col_headers = list(cross_df.columns)
        lines.append(
            "| "
            + group_field.capitalize()
            + " | "
            + " | ".join(str(c) for c in col_headers)
            + " |"
        )
        lines.append("|---" + "|---" * len(col_headers) + "|")
        for idx, row in cross_df.iterrows():
            vals = " | ".join(f"{v:.4f}" if pd.notna(v) else "N/A" for v in row)
            lines.append(f"| {idx} | {vals} |")
    else:
        lines.append("*Cross-table not available (single group or insufficient data).*")
    lines.append("")

    # Section 5: Conclusions
    lines.append("## 5. Conclusions")
    lines.append("")
    for i, c in enumerate(conclusions, 1):
        lines.append(f"{i}. {c}")
    lines.append("")

    return "\n".join(lines)


def main():
    args = parse_args()

    # Load data
    df = load_records(args.log, args.filter)

    if df.empty:
        print("Error: no records found after filtering.", file=sys.stderr)
        sys.exit(1)

    # Validate required fields
    for field_name, field_val in [
        ("--method-field", args.method_field),
        ("--metric-field", args.metric_field),
        ("--group-field", args.group_field),
    ]:
        if field_val not in df.columns:
            print(
                f"Error: field '{field_val}' (from {field_name}) not found in log data. "
                f"Available columns: {list(df.columns)}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Compute components
    summary = compute_summary(
        df, args.method_field, args.metric_field, args.group_field
    )
    ranking_df = compute_method_ranking(
        df,
        args.method_field,
        args.metric_field,
        args.runtime_field,
        args.lower_is_better,
    )
    cross_df = compute_cross_table(
        df, args.method_field, args.metric_field, args.group_field
    )

    # Generate narrative (with optional overrides)
    auto_overview, auto_findings, auto_conclusions = generate_narrative(
        summary, ranking_df, cross_df, args.lower_is_better
    )

    overview = args.overview if args.overview is not None else auto_overview
    findings = (
        [f.strip() for f in args.findings.split(";")]
        if args.findings is not None
        else auto_findings
    )
    conclusions = (
        [c.strip() for c in args.conclusions.split(";")]
        if args.conclusions is not None
        else auto_conclusions
    )

    # Format Markdown
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_md = format_markdown(
        args.title,
        timestamp,
        overview,
        findings,
        conclusions,
        summary,
        ranking_df,
        cross_df,
    )

    # Write output
    os.makedirs(args.output_dir, exist_ok=True)
    if args.output_name is not None:
        out_filename = args.output_name
    else:
        stem = os.path.splitext(os.path.basename(args.log))[0]
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_filename = f"{stem}_{ts}.md"

    out_path = os.path.join(args.output_dir, out_filename)
    with open(out_path, "w") as f:
        f.write(report_md)

    print(f"Report written to: {out_path}")


if __name__ == "__main__":
    main()
