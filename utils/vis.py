import json
import networkx as nx
import matplotlib.pyplot as plt
from pathlib import Path

# Load the slicing JSON file
file_path = "/data/DataLACP/wangke/recorebench/workspace/HikariCP/slicing.json"
output_path = "/data/DataLACP/wangke/recorebench/workspace/HikariCP/slice_visualization.png"
with open(file_path, "r") as f:
    slice_data = json.load(f)

# Create a directed graph
G = nx.DiGraph()

# Add nodes with labels
node_labels = {}
for node in slice_data.get("nodes", []):
    node_id = node["id"]
    label = f'{node["name"] if "name" in node else node["label"]}\n({node["code"]})'
    G.add_node(node_id, label=label)
    node_labels[node_id] = label

# Add edges with labels
for edge in slice_data.get("edges", []):
    src = edge["src"]
    dst = edge["dst"]
    # label = edge["label"]
    G.add_edge(src, dst)

# Draw the graph
pos = nx.spring_layout(G)
plt.figure(figsize=(16, 12))
nx.draw(G, pos, with_labels=True, labels=node_labels, node_size=3000, node_color="lightblue", font_size=8)
edge_labels = nx.get_edge_attributes(G, 'label')
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)
plt.title("Joern Slice Visualization")
plt.axis("off")
# plt.show()
plt.title("Joern Slice Visualization")
plt.axis("off")
plt.tight_layout()
plt.savefig(output_path, dpi=300)
