import os

from enum import Enum, auto

from natpi import NautilusPilot

from textual.app import App
from textual.widgets import Button, Static, RichLog, Input, Label, Checkbox
from textual.containers import Vertical, Horizontal
from textual.color import Color
from textual.reactive import reactive


class Wheelhouse(App):
    class State(Enum):
        MAIN = auto()
        NEW_PIN = auto()
        DELETE_PIN = auto()

    class Status(Static):
        is_online = reactive(False)

        def status_string(self):
            if self.is_online:
                return "Status:  [green]Online[/green]"
            else:
                return "Status: [red]Offline[/red]"

        def render(self):
            return self.status_string()

    class NewPinForm(Static):
        def compose(self):
            yield Vertical(
                Horizontal(
                    Label("Name:"),
                    Input(id="pin-name-input"),
                ),
                Horizontal(
                    Label("Latitude:"),
                    Input(id="pin-latitude-input"),
                ),
                Horizontal(
                    Label("Longitude:"),
                    Input(id="pin-longitude-input"),
                ),
                Horizontal(
                    Label("Add to route:"),
                    Checkbox(id="pin-add-to-route-checkbox"),
                ),
                Horizontal(
                    Button("🌟 Add", id="add-pin-button", variant="success"),
                    Button("🌟 Cancel", id="cancel-pin-button", variant="warning"),
                ),
                id="new-pin-form",
            )

    CSS_PATH = "wheelhouse-style.tcss"

    is_online = reactive(False)

    def __init__(self):
        super().__init__()

        self.natpi = NautilusPilot()
        self.state = Wheelhouse.State.MAIN

    def sail(self):
        self.run()

    def compose(self):
        yield Static("Nautilus Pilot", id="title")
        yield Vertical(
            Wheelhouse.Status().data_bind(is_online=self.is_online),
            Button(
                "🌟 Switch",
                id="switch-button",
                classes="main-buttons",
                variant="primary",
            ),
            Button(
                "🌟 New pin",
                id="new-pin-button",
                classes="main-buttons",
                variant="primary",
            ),
            Button(
                "🌟 Delete pin",
                id="delete-pin-button",
                classes="main-buttons",
                variant="primary",
            ),
            Button(
                "🌟 Leave", id="leave-button", classes="main-buttons", variant="primary"
            ),
            id="main-container",
        )
        yield Wheelhouse.NewPinForm()
        yield RichLog()

    def on_mount(self):
        # main
        self.main_container = self.query_one("#main-container")
        self.status = self.query_one(Wheelhouse.Status)

        self.switch = self.query_one("#switch-button")
        self.new_pin = self.query_one("#new-pin-button")
        self.delete_pin = self.query_one("#delete-pin-button")
        self.leave = self.query_one("#leave-button")
        self.main_focusables = [self.switch, self.new_pin, self.delete_pin, self.leave]

        self.rich_log = self.query_one(RichLog)
        self.rich_log.can_focus = False
        self.rich_log.write("Welcome to Nautilus Pilot!")

        # new pin form
        self.new_pin_form = self.query_one(Wheelhouse.NewPinForm)
        self.new_pin_form.visible = False
        self.name_input = self.query_one("#pin-name-input")
        self.latitude_input = self.query_one("#pin-latitude-input")
        self.longitude_input = self.query_one("#pin-longitude-input")
        self.add_to_route_checkbox = self.query_one("#pin-add-to-route-checkbox")
        self.add_pin_button = self.query_one("#add-pin-button")
        self.cancel_pin_button = self.query_one("#cancel-pin-button")

        self.new_pin_form_focusables = [
            self.name_input,
            self.latitude_input,
            self.longitude_input,
            self.add_to_route_checkbox,
            self.add_pin_button,
            self.cancel_pin_button,
        ]

        ### delete pin form
        self.delete_pin_form_focusables = []

        self.all_focusables = (
            self.main_focusables
            + self.new_pin_form_focusables
            + self.delete_pin_form_focusables
        )
        self.focusables = self.main_focusables

    def change_state(self, new_state):
        self.state = new_state
        if self.state == Wheelhouse.State.MAIN:
            self.focusables = self.main_focusables
        elif self.state == Wheelhouse.State.NEW_PIN:
            self.focusables = self.new_pin_form_focusables
        elif self.state == Wheelhouse.State.DELETE_PIN:
            self.focusables = self.delete_pin_form_focusables
        self.update_focusable()
        self.focusables[0].focus()

    def update_focusable(self):
        for widget in self.all_focusables:
            widget.can_focus = False

        for widget in self.focusables:
            widget.can_focus = True

    def current_focus(self):
        for i, widget in enumerate(self.focusables):
            if widget.has_focus:
                return i
        raise ValueError("No widget has focus")

    def next_focus(self):
        current_focus = self.current_focus()
        next_focus = min(len(self.focusables) - 1, current_focus + 1)
        self.focusables[next_focus].focus()

    def previous_focus(self):
        current_focus = self.current_focus()
        next_focus = max(0, current_focus - 1)
        self.focusables[next_focus].focus()

    def on_key(self, event):
        self.rich_log.write(event)

        match event.key:
            case "up":
                self.previous_focus()
            case "down":
                self.next_focus()
            case "left":
                if self.state == Wheelhouse.State.NEW_PIN:
                    current_focus = self.current_focus()
                    if current_focus == len(self.new_pin_form_focusables) - 1:
                        self.previous_focus()
            case "right":
                if self.state == Wheelhouse.State.NEW_PIN:
                    current_focus = self.current_focus()
                    if current_focus == len(self.new_pin_form_focusables) - 2:
                        self.next_focus()

    def on_button_pressed(self, event):
        match event.button:
            case self.switch:
                self.status.is_online = not self.status.is_online
            case self.new_pin:
                self.new_pin_form.visible = True
                self.change_state(Wheelhouse.State.NEW_PIN)
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
