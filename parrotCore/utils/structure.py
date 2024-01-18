
class TreeNode:
    def __init__(self, value, depth, father):
        self.value = value
        self.depth = depth
        self.father = father
        self.children = []