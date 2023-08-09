from typing import List
from promptflow import tool


@tool
def aggregate(processed_results: List[str]):
    """
    This tool aggregates the processed result of all lines and log metric.

    :param processed_results: List of the output of line_process node.
    """

    # Add your aggregation logic here, for example:
    total_lines = len(processed_results)
    right_lines = 0
    for line in processed_results:
        if line == "right":
            right_lines += 1

    aggregated_results = {
        "total_lines": total_lines,
        "right_lines": right_lines,
    }

    # Add your metric logging logic here, for example:
    from promptflow import log_metric
    log_metric(key="accuracy", value=right_lines / total_lines)

    return aggregated_results