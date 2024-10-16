import os
from natpi import NautilusPilot

from textual.app import App
from textual.widgets import Button, Static, RichLog, Input, Label
from textual.containers import ScrollableContainer, Vertical
from textual.color import Color
from textual.reactive import reactive


class Status(Static):
    is_online = reactive(False)

    def status_string(self):
        if self.is_online:
            return "Status:  [green]Online[/green]"
        else:
            return "Status: [red]Offline[/red]"

    def render(self):
        return self.status_string()


class Wheelhouse(App):
    CSS_PATH = "wheelhouse-style.tcss"

    is_online = reactive(False)

    def __init__(self):
        super().__init__()

        self.natpi = NautilusPilot()

    def sail(self):
        self.run()

    def compose(self):
        yield Static("Nautilus Pilot", id="title")
        yield Vertical(
            Status().data_bind(is_online=self.is_online),
            Button("🌟 Switch", id="switch-button", variant="primary"),
            Button("🌟 New pin", id="new-pin-button", variant="primary"),
            Button("🌟 Delete pin", id="delete-pin-button", variant="primary"),
            Button("🌟 Leave", id="leave-button", variant="primary"),
            id="vertical",
        )
        yield RichLog()

    def on_mount(self):
        self.status = self.query_one(Status)

        self.switch = self.query_one("#switch-button")
        self.new_pin = self.query_one("#new-pin-button")
        self.delete_pin = self.query_one("#delete-pin-button")
        self.leave = self.query_one("#leave-button")
        self.buttons = [self.switch, self.new_pin, self.delete_pin, self.leave]

        self.rich_log = self.query_one(RichLog)

        self.rich_log.can_focus = False
        self.rich_log.write("Welcome to Nautilus Pilot!")

    def current_focus(self):
        i = 0
        while i < len(self.buttons):
            if self.buttons[i].has_focus:
                return i
            i += 1
        raise Exception("No button focused")

    def on_key(self, event):
        self.rich_log.write(event)

        if event.key == "up":
            current_focus = self.current_focus()
            next_focus = max(0, current_focus - 1)
            self.buttons[next_focus].focus()
        elif event.key == "down":
            current_focus = self.current_focus()
            next_focus = min(len(self.buttons) - 1, current_focus + 1)
            self.buttons[next_focus].focus()

    def on_button_pressed(self, event):
        match event.button:
            case self.switch:
                self.status.is_online = not self.status.is_online
            case self.new_pin:
                self.rich_log.write("New pin button pressed!")
            case self.delete_pin:
                self.rich_log.write("Delete pin button pressed!")
            case self.leave:
                self.rich_log.write("Leave button pressed!")
            case _:
                self.rich_log.write("Unknown button pressed!")


def main():
    wheelhouse = Wheelhouse()
    wheelhouse.sail()


if __name__ == "__main__":
    main()
