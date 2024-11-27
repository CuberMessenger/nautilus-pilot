import os
import io
import json
import time
import base64

import simplekml
import numpy as np

from PIL import Image
from time import sleep
from enum import Enum, auto

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

from textual.app import App
from textual.widgets import Button, Static, Input, Label, Checkbox, Switch
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive


class NautilusPilot:
    JS_DRAG_AND_DROP = """
        var b64File = '{}';
        var filename = '{}';
        var contentType = 'text/plain';

        var binary = atob(b64File);
        var array = [];
        for (var i = 0; i < binary.length; i++) {{
            array.push(binary.charCodeAt(i));
        }}
        var uint8Array = new Uint8Array(array);

        var file = new File([uint8Array], filename, {{type: contentType}});

        var dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);

        var canvas = arguments[0];

        ['dragenter', 'dragover', 'drop'].forEach(function(eventName) {{
            var event = new DragEvent(eventName, {{
                dataTransfer: dataTransfer,
                bubbles: true,
                cancelable: true
            }});
            canvas.dispatchEvent(event);
        }});
    """

    JSON_PATH = "data.json"

    KML_PATH = "data.kml"

    @staticmethod
    def update_kml():
        with open(NautilusPilot.JSON_PATH, "r") as json_file:
            json_data = json.load(json_file)

        kml = simplekml.Kml()

        # points
        for point in json_data["points"]:
            kml.newpoint(
                name=point["name"],
                coords=[(point["longitude"], point["latitude"])],
            )

        # routes
        line = kml.newlinestring(
            coords=[
                (point["longitude"], point["latitude"])
                for point in json_data["route_points"]
            ],
        )

        line.style.linestyle.color = "FFFEE7A6"
        line.style.linestyle.width = 4

        kml.save(NautilusPilot.KML_PATH)

    @staticmethod
    def add_point(name, latitude, longitude, add_to_route):
        with open(NautilusPilot.JSON_PATH, "r") as json_file:
            json_data = json.load(json_file)

        point = {"name": name, "latitude": latitude, "longitude": longitude}

        if not add_to_route:
            json_data["points"].append(point)
        else:
            json_data["route_points"].append(point)

        with open(NautilusPilot.JSON_PATH, "w") as json_file:
            json.dump(json_data, json_file)

    @staticmethod
    def remove_point(name, from_route):
        with open(NautilusPilot.JSON_PATH, "r") as json_file:
            json_data = json.load(json_file)

        if not from_route:
            points = json_data["points"]
        else:
            points = json_data["route_points"]

        if name == "":
            # try to remove the last point
            index = len(points) - 1
            if index >= 0:
                points.pop(index)
                success = True
                message = "Last pin removed!"
            else:
                success = False
                message = "No pins to remove!"
        if name != "":
            # remove the last occurrence
            index = None
            for i, point in enumerate(reversed(points)):
                if point["name"] == name:
                    index = len(points) - 1 - i
                    break

            if index is None:
                success = False
                message = f"No such pin!"
            else:
                points.pop(index)
                success = True
                message = f"{name} removed!"

        with open(NautilusPilot.JSON_PATH, "w") as json_file:
            json.dump(json_data, json_file)

        return success, message

    def __init__(self):
        self.driver = None
        self.canvas = None

    # DEPRECATED
    def screenshot(self):
        image_data = self.driver.get_screenshot_as_png()
        image = Image.open(io.BytesIO(image_data))
        image = np.array(image)

        return image

    # DEPRECATED
    def find_sidebar_button(self, image):
        pixel_tolerance = 10
        default_gray = np.array([70, 71, 68])

        height, width, _ = image.shape
        canvas_height, canvas_width = (
            self.canvas.size["height"],
            self.canvas.size["width"],
        )

        top_bar_height = 72
        # top_bar_height = 0
        # while (image[top_bar_height, -1] == 255).all():
        #     top_bar_height += 1

        # image = image[top_bar_height:, :, :]

        col = 0
        row = int(round((height - top_bar_height) / 2 + top_bar_height))
        for try_col in range(width // 2):
            if np.sum(np.abs(image[row, try_col] - default_gray)) < pixel_tolerance:
                col = try_col
                break
            # image[row, try_col] = np.array([0, 255, 0])

        # Image.fromarray(image).save("test-sidebar.png")

        if col == 0:
            raise Exception("Could not find the sidebar button!")

        is_open = col > top_bar_height

        col = int(round(col * canvas_width / width))
        row = int(round(row * canvas_height / height))

        col_offset = col - canvas_width // 2
        row_offset = row - canvas_height // 2
        return col_offset, row_offset, is_open

    # DEPRECATED
    def find_hide_button(self, image):
        pixel_tolerance = 10
        dark_gray = np.array([31, 31, 31])
        light_gray = np.array([233, 233, 233])
        white = np.array([255, 255, 255])

        height, width, _ = image.shape
        canvas_height, canvas_width = (
            self.canvas.size["height"],
            self.canvas.size["width"],
        )

        top_bar_height = 72

        col = 52
        row = int(round((height - top_bar_height) / 2 + top_bar_height))
        for offset in range(256):
            if np.sum(np.abs(image[row + offset, col] - dark_gray)) < pixel_tolerance:
                break
            # image[row + offset, col] = np.array([255, 0, 0])
        row += offset

        for offset in range(512):
            if np.sum(np.abs(image[row, col + offset] - white)) < pixel_tolerance:
                break
            # image[row, col + offset] = np.array([255, 0, 0])
        col += offset

        col -= 32

        # length = 5
        # image[row - length : row + length, col - length : col + length] = np.array([255, 0, 0])
        # Image.fromarray(image).save("test-hide.png")

        col = int(round(col * canvas_width / width))
        row = int(round(row * canvas_height / height))

        col_offset = col - canvas_width // 2
        row_offset = row - canvas_height // 2

        return col_offset, row_offset

    # DEPRECATED
    def update(self, is_first=False):
        if self.driver is None or self.canvas is None:
            return

        NautilusPilot.update_kml()

        with open(NautilusPilot.KML_PATH, mode="r") as file:
            content = file.read()
            b64_content = base64.b64encode(content.encode()).decode()

        image = self.screenshot()
        col_offset, row_offset, is_open = self.find_sidebar_button(image)

        if not is_open:
            # Open the sidebar
            ActionChains(self.driver).move_to_element_with_offset(
                self.canvas, col_offset, row_offset
            ).click().perform()
            sleep(0.5)  # wait the sidebar fully open

            image = self.screenshot()

        if not is_first:
            hide_col_offset, hide_row_offset = self.find_hide_button(image)
            try:
                # Try hide existing route
                ActionChains(self.driver).move_to_element_with_offset(
                    self.canvas, hide_col_offset, hide_row_offset
                ).click().perform()
            except:
                pass

        self.driver.execute_script(
            NautilusPilot.JS_DRAG_AND_DROP.format(
                b64_content, os.path.basename(NautilusPilot.KML_PATH)
            ),
            self.canvas,
        )

        col_offset, row_offset, _ = self.find_sidebar_button(image)

        # Close the sidebar
        ActionChains(self.driver).move_to_element_with_offset(
            self.canvas, col_offset, row_offset
        ).click().perform()

    def start_browser(self):
        local_user_data_folder = os.path.join(os.getcwd(), "Local")
        if not os.path.exists(local_user_data_folder):
            os.makedirs(local_user_data_folder)

        options = webdriver.EdgeOptions()
        options.add_argument(f"user-data-dir={local_user_data_folder}")
        options.add_argument("--disable-infobars")

        service = Service("msedgedriver.exe")

        self.driver = webdriver.Edge(service=service, options=options)
        self.driver.get("https://earth.google.com/web")

        # WebDriverWait(self.driver, 30).until(
        #     lambda driver: driver.current_url.find("@") != -1
        # )

        # self.canvas = self.driver.find_element(By.ID, "earth-canvas")
        # self.canvas.click()
        # self.update(is_first=True)

    def stop_browser(self):
        self.driver.quit()
        self.driver = None
        self.canvas = None


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
