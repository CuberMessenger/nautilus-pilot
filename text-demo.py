from typing import Coroutine
from textual.app import App
from textual.widgets import Header, Footer, Static, RichLog, Input
from textual.containers import ScrollableContainer

class TextDemo(App):

    # BINDINGS = [
    #     ("ESE", "quit", "Quit"),
    # ]

    def compose(self):
        yield Header()
        yield Static("Hello, World!")
        # yield RichLog()
        yield ScrollableContainer(Input(), Input(), Input())
        # yield Footer()

    # def on_key(self, event):
    #     self.query_one(RichLog).write(event)





if __name__ == "__main__":
    text_demo = TextDemo()
    text_demo.run()

