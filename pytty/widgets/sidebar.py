from textual.message import Message
from textual.widget import Widget
from textual.widgets import Tree

from pytty.config import load_servers


class ServerSelected(Message):
    def __init__(self, name: str, host: str, user: str, port: int) -> None:
        self.name = name
        self.host = host
        self.user = user
        self.port = port
        super().__init__()


class Sidebar(Widget):
    def compose(self):
        yield Tree("Servers", id="server-tree")

    def on_mount(self):
        tree = self.query_one("#server-tree", Tree)
        data = load_servers()
        for group in data.get("groups", []):
            group_node = tree.root.add(group["name"], expand=True)
            for server in group.get("servers", []):
                group_node.add_leaf(
                    server["name"],
                    data={
                        "name": server["name"],
                        "host": server["host"],
                        "user": server["user"],
                        "port": server.get("port", 22),
                    },
                )
        tree.root.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected):
        node = event.node
        if node.data and "host" in node.data:
            self.post_message(
                ServerSelected(
                    name=node.data["name"],
                    host=node.data["host"],
                    user=node.data["user"],
                    port=node.data["port"],
                )
            )
