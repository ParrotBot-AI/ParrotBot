class TreeNode:
    def __init__(self, attributes):
        for key, value in attributes.items():
            setattr(self, key, value)  # Dynamically set attributes based on dictionary keys
        self.children = []

    def add_child(self, child_node):
        """Add a child node to this node."""
        self.children.append(child_node)

    def __repr__(self):
        """Representation of the node, showing its attributes and children."""
        attributes = vars(self).copy()
        # Convert children to a list of their repr
        attributes['children'] = [repr(child) for child in self.children]
        return str(attributes)

    def to_dict(self):
        """Return a dictionary representation of the node, including its attributes and children."""
        attributes = vars(self).copy()  # Copy attributes to include in the dictionary
        attributes['children'] = [child.to_dict() for child in self.children]  # Recursively convert children
        return attributes


class Tree:
    def __init__(self):
        self.roots = []

    def add_root(self, attributes):
        """Add a new root to the tree."""
        new_root = TreeNode(attributes)
        self.roots.append(new_root)
        return new_root

    def add_node(self, parent_attribute, parent_value, child_attributes):
        """Add a node under the node with the specified parent attribute and value."""
        for root in self.roots:
            parent_node = self._find_node_by_attribute(root, parent_attribute, parent_value)
            if parent_node is not None:
                parent_node.add_child(TreeNode(child_attributes))
                return
        # If no parent found, create a new root
        self.add_root(child_attributes)

    def _find_node_by_attribute(self, current_node, attribute, value):
        """Helper method to find a node with the given attribute and value."""
        if hasattr(current_node, attribute) and getattr(current_node, attribute) == value:
            return current_node
        for child in current_node.children:
            node = self._find_node_by_attribute(child, attribute, value)
            if node:
                return node
        return None

    def print_tree(self, start_node=None):
        """Return a list of dictionaries representing the tree from each root."""
        return [root.to_dict() for root in self.roots]

    def sum_children_scores(self, node):
        # Base case: if the node has no children, return its score
        if not node.children:
            return node.score

        # Recursive case: the node has children, so sum their scores
        total_score = 0
        for child in node.children:
            total_score += self.sum_children_scores(child)

        # Update the current node's score to be the sum of its children's scores
        node.score = total_score
        return node.score




if __name__ == "__main__":
    # Example usage
    tree = Tree()
    tree.add_root({"order1": 1, "content": "root1"})
    tree.add_node("order1", 1, {"order1": 2, "content": "child1"})
    tree.add_node("order1", 2, {"order1": 3, "content": "child2"})
    tree.add_root({"order": 1, "content": "root2"})
    tree.print_tree()
