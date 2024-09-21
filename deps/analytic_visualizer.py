"""
Code to show the relationsip between the users
"""

import io

# pylint: disable=import-error
import networkx as nx
import matplotlib.pyplot as plt
import community as community_louvain
from deps.analytic_gatherer import calculate_time_spent_from_db
from deps.analytic import cursor


def _get_data(from_day, to_day) -> list:
    """
    Display the relationship between users in a graph
    """
    calculate_time_spent_from_db(from_day, to_day)
    # Fetch the data from the user_weights table
    cursor.execute(
        """
    SELECT ui1.display_name as user_a_display_name, ui2.display_name as user_b_display_name, weight 
    FROM user_weights 
    left join user_info as ui1 on user_weights.user_a = ui1.id 
    left join user_info as ui2 on user_weights.user_b = ui2.id
    """
    )
    data = cursor.fetchall()
    return data


def display_graph_network_relationship(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
    """
    Display the relationship between users in a graph
    """
    data = _get_data(from_day, to_day)
    # Extract weights for normalization
    weights = [weight for _, _, weight in data]
    max_weight = max(weights)

    # Create a graph using NetworkX
    graph_network = nx.Graph()

    # Add edges with weights between users
    for user_a_display_name, user_b_display_name, weight in data:
        normalized_weight = (weight / max_weight) * 100  # Normalize to max 100
        graph_network.add_edge(user_a_display_name, user_b_display_name, weight=normalized_weight)

    # Draw the graph
    plt.figure(figsize=(10, 10))

    # Position the nodes using the spring layout for a better spread
    pos = nx.spring_layout(graph_network)

    # Draw nodes
    nx.draw_networkx_nodes(graph_network, pos, node_size=700, node_color="skyblue")

    # Draw edges, adjusting width based on the weight
    weights = nx.get_edge_attributes(graph_network, "weight")
    nx.draw_networkx_edges(graph_network, pos, width=[w / 10 for w in weights.values()])

    # Draw labels for users (nodes)
    nx.draw_networkx_labels(graph_network, pos, font_size=12, font_family="sans-serif")

    # Draw edge labels (weights)
    nx.draw_networkx_edge_labels(graph_network, pos, edge_labels={k: f"{v:.2f}" for k, v in weights.items()})

    # Show plot
    plt.title("User Relationship Graph (Edge Tickness = More Time Together)")
    plt.axis("off")  # Turn off the axis
    return _plot_return(plt, show)


def display_graph_cluster_people(show: bool = True, from_day: int = 3600, to_day: int = 0) -> None:
    """
    Determine the clusters of users and display them in a graph
    """
    data = _get_data(from_day, to_day)
    weights = [weight for _, _, weight in data]
    max_weight = max(weights)

    # Create a graph using NetworkX
    graph_network = nx.Graph()

    # Add edges with normalized weights between users
    for user_a, user_b, weight in data:
        normalized_weight = (weight / max_weight) * 100  # Normalize to max 100
        graph_network.add_edge(user_a, user_b, weight=normalized_weight)

    # Detect communities using Louvain method
    partition = community_louvain.best_partition(graph_network)

    # Get unique community IDs and colors for visualization
    communities = set(partition.values())
    colors = plt.cm.get_cmap("viridis", len(communities))

    # Draw the graph
    plt.figure(figsize=(12, 12))

    # Position the nodes using the spring layout
    pos = nx.spring_layout(graph_network)

    # Draw nodes, coloring by community
    for community_id in communities:
        nodes_in_community = [node for node in partition if partition[node] == community_id]
        nx.draw_networkx_nodes(
            graph_network,
            pos,
            nodelist=nodes_in_community,
            node_color=[colors(community_id)],
            label=f"Community {community_id}",
            node_size=700,
        )

    # Draw edges, adjusting width based on the normalized weight
    normalized_weights = nx.get_edge_attributes(graph_network, "weight")
    nx.draw_networkx_edges(graph_network, pos, width=[w / 10 for w in normalized_weights.values()])

    # Draw labels for users (nodes), adjusted to be above the nodes
    label_pos = {node: (x, y + 0.05) for node, (x, y) in pos.items()}  # Adjust y-coordinate
    nx.draw_networkx_labels(
        graph_network,
        label_pos,
        labels={node: node for node in graph_network.nodes()},
        font_size=12,
        font_family="sans-serif",
    )

    # Draw edge labels (normalized weights)
    nx.draw_networkx_edge_labels(graph_network, pos, edge_labels={k: f"{v:.2f}" for k, v in normalized_weights.items()})

    # Show plot
    plt.title("User Relationship Graph with Clusters (Edge Tickness = More Time Together)")
    plt.axis("off")  # Turn off the axis
    plt.legend()
    return _plot_return(plt, show)


def _plot_return(plot: plt, show: bool = True):
    """
    Return an image or the bytes of the iamge
    """
    if show:
        plot.show()
        return None

    buf = io.BytesIO()
    plot.savefig(buf, format="png")
    buf.seek(0)

    # Get the bytes data
    image_bytes = buf.getvalue()
    buf.close()
    return image_bytes
