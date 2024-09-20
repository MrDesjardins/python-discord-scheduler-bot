"""
Code to show the relationsip between the users
"""
# pylint: disable=import-error
import networkx as nx
import matplotlib.pyplot as plt
from analytic import cursor


def display_graph_network_relationship() -> None:
    # Fetch the data from the user_weights table
    cursor.execute(
        """
  SELECT user_a, user_b, weight FROM user_weights
  """
    )
    data = cursor.fetchall()

    # Create a graph using NetworkX
    G = nx.Graph()

    # Add edges with weights between users
    for user_a, user_b, weight in data:
        G.add_edge(user_a, user_b, weight=weight)

    # Draw the graph
    plt.figure(figsize=(10, 10))

    # Position the nodes using the spring layout for a better spread
    pos = nx.spring_layout(G)

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=700, node_color="skyblue")

    # Draw edges, adjusting width based on the weight
    weights = nx.get_edge_attributes(G, "weight")
    nx.draw_networkx_edges(G, pos, width=[w / 10 for w in weights.values()])

    # Draw labels for users (nodes)
    nx.draw_networkx_labels(G, pos, font_size=12, font_family="sans-serif")

    # Draw edge labels (weights)
    nx.draw_networkx_edge_labels(G, pos, edge_labels={k: f"{v:.2f}" for k, v in weights.items()})

    # Show plot
    plt.title("User Relationship Graph (Edge Weight = Time Spent Together)")
    plt.axis("off")  # Turn off the axis
    plt.show()
