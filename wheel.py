import os
import time

from enum import Enum, auto

from natpi import NautilusPilot

from textual import work
from textual.app import App
from textual.widgets import Button, Static, RichLog, Input, Label, Checkbox, Switch
from textual.containers import Vertical, Horizontal
from textual.color import Color
from textual.reactive import reactive


class Wheelhouse(App):
    class State(Enum):
        MAIN = auto()
        NEW_PIN = auto()
        REMOVE_PIN = auto()

    class Status(Static):
        is_online = reactive(False)

        def status_string(self):
            if self.is_online:
                return "Status:  [green]Online[/green]"
            else:
                return "Status: [red]Offline[/red]"

        def render(self):
            return self.status_string()

    class ItudeInput(Static):
        DEFAULT_CSS = """
        .degree-input {
            width: 10;
        }

        .minute-input {
            width: 10;
            padding-left: 4;
        }

        .direction-switch {
            width: 10;
        }

        .itude-input-label {
            padding-top: 1;
        }
        """

        def __init__(self, type="latitude", id=None):
            super().__init__(id=id)

            self.type = type

            if type == "latitude":
                self.direction_a = "N"
                self.direction_b = "S"
            elif type == "longitude":
                self.direction_a = "E"
                self.direction_b = "W"
            else:
                raise ValueError("type must be 'latitude' or 'longitude'")

        def compose(self):
            yield Horizontal(
                Input(
                    type="number",
                    max_length=3,
                    classes="degree-input",
                    id=f"{self.type}-degree-input",
                    valid_empty=True,
                ),
                Label("degrees", classes="itude-input-label"),
                Input(
                    type="number",
                    max_length=2,
                    classes="minute-input",
                    id=f"{self.type}-minute-input",
                    valid_empty=True,
                ),
                Label("minutes", classes="itude-input-label"),
                Switch(
                    value=False,
                    classes="direction-switch",
                    id=f"{self.type}-direction-switch",
                ),
                Label(
                    self.direction_a,
                    classes="itude-input-label",
                    id="itude-switch-label",
                ),
            )

        def on_switch_changed(self, event):
            label = self.query_one("#itude-switch-label")
            label.render = lambda: (
                self.direction_b if event.value else self.direction_a
            )
            label.refresh()

    class NewPinForm(Static):
        DEFAULT_CSS = """
        .pin-form-label {
            margin-top: 1;
        }

        #pin-name-input {
            width: 44;
            margin-right: 2;
        }

        #pin-latitude-input {
            width: 46;
        }

        #pin-longitude-input {
            width: 46;
        }

        #pin-add-to-route-checkbox {
            width: 44;
            margin-left: 8;
            text-align: center;
        }

        #add-pin-button {
            width: 21;
            margin-left: 9;
        }

        #cancel-pin-button {
            width: 21;
        }

        .itude-input {
            height: 3;
        }
        """

        def compose(self):
            yield Vertical(
                Horizontal(
                    Label("          *** Add a new pin! ***"),
                ),
                Horizontal(
                    Label("     Name:", classes="pin-form-label"),
                    Input(id="pin-name-input", type="text"),
                ),
                Horizontal(
                    Label(" Latitude:", classes="pin-form-label"),
                    Wheelhouse.ItudeInput(type="latitude", id="pin-latitude-input"),
                ),
                Horizontal(
                    Label("Longitude:", classes="pin-form-label"),
                    Wheelhouse.ItudeInput(type="longitude", id="pin-longitude-input"),
                ),
                Horizontal(
                    Checkbox(
                        label="Add to route", id="pin-add-to-route-checkbox", value=True
                    ),
                ),
                Horizontal(
                    Button("🌟 Add", id="add-pin-button", variant="success"),
                    Button("🌟 Cancel", id="cancel-pin-button", variant="warning"),
                ),
                id="new-pin-form",
            )

    class RemovePinForm(Static):
        DEFAULT_CSS = """
        .pin-form-label {
            margin-top: 1;
        }

        #remove-name-input {
            width: 44;
            margin-right: 2;
        }

        #pin-remove-from-route-checkbox {
            width: 44;
            margin-left: 8;
            text-align: center;
        }

        #remove-button {
            width: 21;
            margin-left: 9;
        }

        #cancel-remove-button {
            width: 21;
        }
        """

        def compose(self):
            yield Vertical(
                Horizontal(
                    Label("          *** Remove a pin! ***"),
                ),
                Horizontal(
                    Label("     Name:", classes="pin-form-label"),
                    Input(id="remove-name-input", type="text"),
                ),
                Horizontal(
                    Checkbox(
                        label="Remove from route",
                        id="pin-remove-from-route-checkbox",
                        value=False,
                    ),
                ),
                Horizontal(
                    Button("🌟 Remove", id="remove-button", variant="error"),
                    Button("🌟 Cancel", id="cancel-remove-button", variant="warning"),
                ),
            )

    is_online = reactive(False)

    CSS_PATH = "wheelhouse-style.tcss"

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
                "🌟 Remove pin",
                id="remove-pin-button",
                classes="main-buttons",
                variant="primary",
            ),
            Button(
                "🌟 Leave", id="leave-button", classes="main-buttons", variant="primary"
            ),
            id="main-container",
        )
        yield Wheelhouse.NewPinForm()
        yield Wheelhouse.RemovePinForm()
        yield Label(id="message-label")

    def on_mount(self):
        # main
        self.main_container = self.query_one("#main-container")
        self.status = self.query_one(Wheelhouse.Status)

        self.switch_button = self.query_one("#switch-button")
        self.new_pin_button = self.query_one("#new-pin-button")
        self.remove_pin_button = self.query_one("#remove-pin-button")
        self.leave_button = self.query_one("#leave-button")
        self.main_focusables = [
            self.switch_button,
            self.new_pin_button,
            self.remove_pin_button,
            self.leave_button,
        ]

        self.message_label = self.query_one("#message-label")
        self.message_label.visible = False

        # new pin form
        self.new_pin_form = self.query_one(Wheelhouse.NewPinForm)
        self.new_pin_form.visible = False
        self.name_input = self.query_one("#pin-name-input")

        self.latitude_degress_input = self.query_one("#latitude-degree-input")
        self.latitude_minutes_input = self.query_one("#latitude-minute-input")
        self.latitude_direction_switch = self.query_one("#latitude-direction-switch")

        self.longitude_degress_input = self.query_one("#longitude-degree-input")
        self.longitude_minutes_input = self.query_one("#longitude-minute-input")
        self.longitude_direction_switch = self.query_one("#longitude-direction-switch")

        self.add_to_route_checkbox = self.query_one("#pin-add-to-route-checkbox")
        self.add_pin_button = self.query_one("#add-pin-button")
        self.cancel_pin_button = self.query_one("#cancel-pin-button")

        self.new_pin_form_focusables = [
            self.name_input,
            self.latitude_degress_input,
            self.latitude_minutes_input,
            self.latitude_direction_switch,
            self.longitude_degress_input,
            self.longitude_minutes_input,
            self.longitude_direction_switch,
            self.add_to_route_checkbox,
            self.add_pin_button,
            self.cancel_pin_button,
        ]

        ### remove pin form
        self.remove_pin_form = self.query_one(Wheelhouse.RemovePinForm)
        self.remove_pin_form.visible = False
        self.remove_name_input = self.query_one("#remove-name-input")
        self.remove_from_route_checkbox = self.query_one(
            "#pin-remove-from-route-checkbox"
        )
        self.remove_button = self.query_one("#remove-button")
        self.cancel_remove_button = self.query_one("#cancel-remove-button")

        self.remove_pin_form_focusables = [
            self.remove_name_input,
            self.remove_from_route_checkbox,
            self.remove_button,
            self.cancel_remove_button,
        ]

        self.all_focusables = (
            self.main_focusables
            + self.new_pin_form_focusables
            + self.remove_pin_form_focusables
        )
        self.focusables = self.main_focusables

    async def show_message(self, message, mississippi=0.75):
        self.message_label.render = lambda: message
        self.message_label.visible = True
        time.sleep(mississippi)
        self.message_label.visible = False

    def change_state(self, new_state):
        old_state = self.state
        self.state = new_state

        match new_state:
            case Wheelhouse.State.MAIN:
                self.focusables = self.main_focusables
            case Wheelhouse.State.NEW_PIN:
                self.focusables = self.new_pin_form_focusables
            case Wheelhouse.State.REMOVE_PIN:
                self.focusables = self.remove_pin_form_focusables
        self.update_focusable()

        match (old_state, new_state):
            case (Wheelhouse.State.MAIN, Wheelhouse.State.NEW_PIN):
                self.new_pin_form.visible = True
                self.name_input.focus()
            case (Wheelhouse.State.MAIN, Wheelhouse.State.REMOVE_PIN):
                self.remove_pin_form.visible = True
                self.remove_name_input.focus()
            case (Wheelhouse.State.NEW_PIN, Wheelhouse.State.MAIN):
                self.new_pin_form.visible = False
                self.clear_new_pin_form()
                self.new_pin_button.focus()
            case (Wheelhouse.State.REMOVE_PIN, Wheelhouse.State.MAIN):
                self.remove_pin_form.visible = False
                self.clear_remove_pin_form()
                self.remove_pin_button.focus()

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
        match event.key:
            case "up":
                if self.state == Wheelhouse.State.NEW_PIN:
                    go_up_cheatsheet = [0, 0, 0, 0, 1, 2, 3, 4, 7, 7]
                    current_focus = self.current_focus()
                    self.focusables[go_up_cheatsheet[current_focus]].focus()
                elif self.state == Wheelhouse.State.REMOVE_PIN:
                    current_focus = self.current_focus()
                    if current_focus in [
                        len(self.remove_pin_form_focusables) - 1,
                        len(self.remove_pin_form_focusables) - 2,
                    ]:
                        self.remove_from_route_checkbox.focus()
                    else:
                        self.previous_focus()
                else:
                    self.previous_focus()

            case "down":
                if self.state == Wheelhouse.State.NEW_PIN:
                    go_down_cheatsheet = [1, 4, 5, 6, 7, 7, 7, 8, 9, 9]
                    current_focus = self.current_focus()
                    self.focusables[go_down_cheatsheet[current_focus]].focus()
                else:
                    self.next_focus()

            case "left":
                if self.state == Wheelhouse.State.NEW_PIN:
                    current_focus = self.current_focus()
                    self.previous_focus()

                if self.state == Wheelhouse.State.REMOVE_PIN:
                    current_focus = self.current_focus()
                    self.previous_focus()
            case "right":
                if self.state == Wheelhouse.State.NEW_PIN:
                    current_focus = self.current_focus()
                    self.next_focus()

                if self.state == Wheelhouse.State.REMOVE_PIN:
                    current_focus = self.current_focus()
                    self.next_focus()
            case "escape":
                if self.state == Wheelhouse.State.NEW_PIN:
                    self.change_state(Wheelhouse.State.MAIN)
                    return
                if self.state == Wheelhouse.State.REMOVE_PIN:
                    self.change_state(Wheelhouse.State.MAIN)
                    return

    ### new pin form funtions #################################################################
    def clear_new_pin_form(self):
        self.name_input.value = ""
        self.latitude_degress_input.value = ""
        self.latitude_minutes_input.value = ""
        self.latitude_direction_switch.value = False
        self.longitude_degress_input.value = ""
        self.longitude_minutes_input.value = ""
        self.longitude_direction_switch.value = False
        self.add_to_route_checkbox.value = False

        self.name_input.refresh()
        self.latitude_degress_input.refresh()
        self.latitude_minutes_input.refresh()
        self.latitude_direction_switch.refresh()
        self.longitude_degress_input.refresh()
        self.longitude_minutes_input.refresh()
        self.longitude_direction_switch.refresh()
        self.add_to_route_checkbox.refresh()

    def add_pin(self):
        try:
            name = self.name_input.value
            if name is None:
                name = ""

            latitude = 0
            latitude += float(self.latitude_degress_input.value)
            latitude += float(self.latitude_minutes_input.value) / 60
            if latitude < 0 or latitude > 90:
                raise ValueError("Latitude out of range!")
            # North is positive, South is negative
            if self.latitude_direction_switch.value:
                latitude = -latitude

            longitude = 0
            longitude += float(self.longitude_degress_input.value)
            longitude += float(self.longitude_minutes_input.value) / 60
            if longitude < 0 or longitude > 180:
                raise ValueError("Longitude out of range!")
            # East is positive, West is negative
            if self.longitude_direction_switch.value:
                longitude = -longitude

            add_to_route = self.add_to_route_checkbox.value
            if add_to_route is None:
                add_to_route = False

            self.natpi.add_point(name, latitude, longitude, add_to_route)

        except Exception:
            return False
        else:
            return True

    ###########################################################################################
    ### remove pin form funtions ##############################################################

    def clear_remove_pin_form(self):
        self.remove_name_input.value = ""
        self.remove_from_route_checkbox.value = False

        self.remove_name_input.refresh()
        self.remove_from_route_checkbox.refresh()

    def remove_pin(self):
        try:
            name = self.remove_name_input.value
            from_route = self.remove_from_route_checkbox.value
            message = self.natpi.remove_point(name, from_route)
        except Exception:
            return "Error!"
        else:
            return message

    ###########################################################################################

    async def on_button_pressed(self, event):
        match event.button:
            # main
            case self.switch_button:
                self.status.is_online = not self.status.is_online
                if self.status.is_online:
                    self.natpi.start_browser()
                else:
                    self.natpi.stop_browser()
            case self.new_pin_button:
                self.change_state(Wheelhouse.State.NEW_PIN)
            case self.remove_pin_button:
                self.change_state(Wheelhouse.State.REMOVE_PIN)
            case self.leave_button:
                try:
                    self.natpi.stop_browser()
                except Exception:
                    pass
                self.exit()
            # new pin form
            case self.add_pin_button:
                success = self.add_pin()

                self.change_state(Wheelhouse.State.MAIN)

                if success:
                    self.run_worker(self.show_message("Pin added!"), thread=True)
                    self.natpi.update()
                else:
                    self.run_worker(self.show_message("Bad input!"), thread=True)
            case self.cancel_pin_button:
                self.change_state(Wheelhouse.State.MAIN)
            # remove pin form
            case self.remove_button:
                success, message = self.remove_pin()

                self.change_state(Wheelhouse.State.MAIN)

                self.run_worker(self.show_message(message), thread=True)
                if success:
                    self.natpi.update()
            case self.cancel_remove_button:
                self.change_state(Wheelhouse.State.MAIN)


def main():
    wheelhouse = Wheelhouse()
    wheelhouse.sail()


if __name__ == "__main__":
    main()
