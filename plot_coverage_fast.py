#!/usr/bin/env python3
import os
import sys
import re
import subprocess
import shutil
import argparse
from pathlib import Path
import matplotlib.pyplot as plt

def parse_queue_files(queue_dir):
    """Parse queue directory and extract timestamps (in seconds)."""
    queue_path = Path(queue_dir)
    if not queue_path.exists():
        raise FileNotFoundError(f"Queue directory not found: {queue_dir}")
    
    queue_files = []
    time_pattern = re.compile(r'time:(\d+)')
    
    for file_path in sorted(queue_path.glob("id:*")):
        match = time_pattern.search(file_path.name)
        if match:
            time_ms = int(match.group(1))
            time_sec = time_ms / 1000.0  # Convert to seconds
            queue_files.append((time_sec, file_path))
    
    queue_files.sort(key=lambda x: x[0])
    return queue_files

def run_coverage_batch(harness_bin, queue_files, profraw_dir):
    """Run all queue files through coverage harness (like coverage.sh)."""
    print(f"[*] Running {len(queue_files)} inputs through coverage harness...")
    
    profraw_dir = Path(profraw_dir)
    if profraw_dir.exists():
        shutil.rmtree(profraw_dir)
    profraw_dir.mkdir(parents=True)
    
    for idx, (time_sec, file_path) in enumerate(queue_files):
        if (idx + 1) % 100 == 0:
            print(f"    Progress: {idx + 1}/{len(queue_files)}")
        
        env = os.environ.copy()
        # Use index as profraw filename so we can track which file it came from
        env["LLVM_PROFILE_FILE"] = str(profraw_dir / f"{idx:06d}.profraw")
        
        with open(file_path, 'rb') as f:
            subprocess.run(
                [str(harness_bin)],
                stdin=f,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                check=False
            )
    
    print(f"[+] Collected {len(list(profraw_dir.glob('*.profraw')))} coverage profiles")

def get_cumulative_coverage(profraw_dir, harness_bin, queue_files, time_shift=0):
    """
    Compute cumulative coverage over time by merging profraw files incrementally.
    
    Returns list of (time, branches_covered, branches_total)
    """
    profraw_dir = Path(profraw_dir)
    profraw_files = sorted(profraw_dir.glob("*.profraw"))
    
    if not profraw_files:
        return []
    
    results = []
    
    # Sample at intervals to speed things up
    sample_points = [0, 10, 20, 50, 100, 200, 500, 1000, len(profraw_files)-1]
    sample_points = [i for i in sample_points if i < len(profraw_files)]
    
    # Always add the last point
    if len(profraw_files) - 1 not in sample_points:
        sample_points.append(len(profraw_files) - 1)
    
    print(f"[*] Computing cumulative coverage at {len(sample_points)} sample points...")
    
    for sample_idx in sample_points:
        # Merge profraw files up to this point
        files_to_merge = profraw_files[:sample_idx + 1]
        
        temp_profdata = profraw_dir.parent / f"temp_{sample_idx}.profdata"
        
        merge_cmd = [
            "llvm-profdata", "merge",
            "-o", str(temp_profdata),
            *[str(f) for f in files_to_merge]
        ]
        subprocess.run(merge_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Get coverage report
        report_cmd = [
            "llvm-cov", "report",
            str(harness_bin),
            f"-instr-profile={temp_profdata}"
        ]
        result = subprocess.run(report_cmd, capture_output=True, text=True, check=True)
        
        # Parse branches
        branches_covered, branches_total = parse_coverage_report(result.stdout)
        
        # Get the time from the corresponding queue file
        time_sec, _ = queue_files[sample_idx]
        adjusted_time = time_sec + time_shift
        
        # For log scale, ensure time is at least 1 second
        if adjusted_time < 1:
            adjusted_time = 1
        
        results.append((adjusted_time, branches_covered, branches_total))
        
        print(f"    File {sample_idx + 1}/{len(profraw_files)}: {branches_covered}/{branches_total} branches at {adjusted_time:.1f}s")
        
        # Clean up temp file
        temp_profdata.unlink()
    
    return results

def parse_coverage_report(report_text):
    """Parse llvm-cov report to extract branch coverage."""
    lines = report_text.strip().split('\n')
    
    for line in reversed(lines):
        if line.startswith('TOTAL'):
            parts = line.split()
            if len(parts) >= 13:
                try:
                    branches_total = int(parts[10])
                    branches_missed = int(parts[11])
                    branches_covered = branches_total - branches_missed
                    return branches_covered, branches_total
                except (ValueError, IndexError):
                    pass
    
    return 0, 0

def plot_comparison(runs_data, labels, output_file, log_scale=False):
    """Generate comparison plot."""
    plt.figure(figsize=(12, 7))
    
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E']
    
    for idx, (run_name, data) in enumerate(runs_data.items()):
        if not data:
            continue
        
        times = [d[0] for d in data]
        branches = [d[1] for d in data]
        
        label = labels.get(run_name, run_name)
        color = colors[idx % len(colors)]
        
        plt.plot(times, branches, marker='o', linewidth=2, 
                markersize=6, label=label, color=color)
    
    if log_scale:
        plt.xscale('log')
        plt.xlabel('Time (seconds, log scale)', fontsize=12, fontweight='bold')
    else:
        plt.xlabel('Time (seconds)', fontsize=12, fontweight='bold')
    
    plt.ylabel('Branch Coverage', fontsize=12, fontweight='bold')
    plt.title('Fuzzer Coverage Comparison Over Time', fontsize=14, fontweight='bold')
    plt.legend(fontsize=11, loc='lower right')
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n[+] Plot saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Fast coverage plotter")
    parser.add_argument("--runs", required=True, help="Colon-separated list of output directories")
    parser.add_argument("--labels", help="Colon-separated list of labels")
    parser.add_argument("--time-shifts", help="Colon-separated list of time shifts in seconds")
    parser.add_argument("--output", default="coverage_comparison.png", help="Output filename")
    parser.add_argument("--harness", default="jsoncpp_fuzz_cov", help="Coverage harness binary")
    parser.add_argument("--log-scale", action="store_true", help="Use logarithmic scale for time axis")
    
    args = parser.parse_args()
    
    # Parse arguments
    runs = args.runs.split(":")
    
    if args.labels:
        labels_list = args.labels.split(":")
        labels = dict(zip(runs, labels_list))
    else:
        labels = {run: f"Run {run}" for run in runs}
    
    if args.time_shifts:
        time_shifts_list = [int(x) for x in args.time_shifts.split(":")]
        time_shifts = dict(zip(runs, time_shifts_list))
    else:
        time_shifts = {run: 0 for run in runs}
    
    # Find harness
    harness_bin = Path(args.harness).resolve()
    if not harness_bin.exists():
        print(f"[!] Harness not found: {harness_bin}")
        print("    Build it first with: python3 plot_coverage.py --runs out2:out3 --rebuild")
        sys.exit(1)
    print(f"[*] Using harness: {harness_bin}")
    
    # Analyze each run
    runs_data = {}
    
    for run in runs:
        print(f"\n{'='*60}")
        print(f"Analyzing: {run}")
        print(f"{'='*60}")
        
        queue_dir = (Path(run) / "default" / "queue").resolve()
        time_shift = time_shifts[run]
        
        try:
            # Parse queue files
            queue_files = parse_queue_files(queue_dir)
            print(f"[+] Found {len(queue_files)} queue files")
            print(f"    Time range: {queue_files[0][0]:.1f}s to {queue_files[-1][0]:.1f}s")
            
            # Run coverage
            profraw_dir = Path(f"temp_{run.replace('/', '_')}_profraw").resolve()
            run_coverage_batch(harness_bin, queue_files, profraw_dir)
            
            # Get cumulative coverage
            data = get_cumulative_coverage(profraw_dir, harness_bin, queue_files, time_shift)
            runs_data[run] = data
            
            # Cleanup
            shutil.rmtree(profraw_dir)
            
        except Exception as e:
            print(f"[!] Error analyzing {run}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Generate plot
    if runs_data:
        plot_comparison(runs_data, labels, args.output, log_scale=args.log_scale)
        print("\n[+] Done!")
    else:
        print("[!] No data collected from any runs")

if __name__ == "__main__":
    main()

