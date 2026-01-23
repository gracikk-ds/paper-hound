"""Statistics chart generation for telegram bot."""

import tempfile
from pathlib import Path

import matplotlib as mpl
from matplotlib import pyplot as plt

# Use non-interactive backend for server environments
mpl.use("Agg")


def generate_monthly_chart(papers_by_month: dict[str, int]) -> Path:
    """Generate bar chart PNG image for papers per month.

    Args:
        papers_by_month: Dictionary mapping "YYYY-MM" to paper count

    Returns:
        Path to generated PNG file in temp directory
    """
    if not papers_by_month:
        msg = "papers_by_month dictionary cannot be empty"
        raise ValueError(msg)

    # Prepare data for plotting
    months = list(papers_by_month.keys())
    counts = list(papers_by_month.values())

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(12, 6))

    # Create bar chart
    bars = ax.bar(months, counts, color="#4A90E2", alpha=0.8, edgecolor="#2E5C8A")

    # Customize chart
    ax.set_xlabel("Month", fontsize=12, fontweight="bold")
    ax.set_ylabel("Number of Papers", fontsize=12, fontweight="bold")
    ax.set_title("Papers Added per Month", fontsize=14, fontweight="bold", pad=20)

    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45, ha="right")

    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{int(height)}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # Add grid for better readability
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)

    # Adjust layout to prevent label cutoff
    plt.tight_layout()

    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        plt.savefig(temp_file.name, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return Path(temp_file.name)
