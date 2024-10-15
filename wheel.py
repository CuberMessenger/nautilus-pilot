import os

from textual.app import App
from textual.widgets import Header, Footer, Static, RichLog, Input
from textual.containers import ScrollableContainer


class Wheelhouse(App):
    def sail(self):
        self.run()

    def compose(self):
        yield Header()
        yield Static("Hello, World!")
        yield ScrollableContainer(Input(), Input(), Input())
        yield RichLog()

    def on_key(self, event):
        self.query_one(RichLog).write(event)


def main():
    wheelhouse = Wheelhouse()
    wheelhouse.sail()


if __name__ == "__main__":
    main()
