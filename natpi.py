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
from selenium.webdriver.common.by import By

from textual.app import App
from textual.widgets import Button, Static, Input, Label, Checkbox, Switch
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive


def color_manhattan(c1, c2):
    return np.sum(abs(c1[i] - c2[i]) for i in range(3))


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

    def update_kml(self):
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
        for route in json_data["routes"]:
            line = kml.newlinestring(
                name=route["name"],
                coords=[
                    (point["longitude"], point["latitude"]) for point in route["points"]
                ],
            )

            line.style.linestyle.color = "FFFEE7A6"
            line.style.linestyle.width = 4

        kml.save(NautilusPilot.KML_PATH)

    def get_route(self, json, route_name):
        for r in json["routes"]:
            if r["name"] == route_name:
                return r
        return None

    def add_point(self, name, route_name, latitude, longitude):
        """
        If route is empty, add the point to the point list.
        If route is not empty, add the point to the route with the given name.
        New route will be created if the route does not exist.
        """
        with open(NautilusPilot.JSON_PATH, "r") as json_file:
            json_data = json.load(json_file)

        point = {"name": name, "latitude": latitude, "longitude": longitude}

        if route_name == "":
            json_data["points"].append(point)
        else:
            route = self.get_route(json_data, route_name)
            if route is None:
                route = {"name": route_name, "points": []}
                json_data["routes"].append(route)

            route["points"].append(point)

        with open(NautilusPilot.JSON_PATH, "w") as json_file:
            json.dump(json_data, json_file)

        self.update_kml()

    def remove_point(self, name, route_name):
        """
        If route is empty, remove from the point list.
        If route is not empty, remove from the route with the given name.
        If route does not exist, return False.

        If name is empty, remove the last point.
        If name is not empty, remove the last occurrence of the name.
        """
        with open(self.JSON_PATH, "r") as json_file:
            json_data = json.load(json_file)

        route = None
        if route_name == "":
            points = json_data["points"]
        else:
            route = self.get_route(json_data, route_name)
            if route is None:
                return False, "No such route!"
            points = route["points"]

        if name == "":
            # try to remove the last point
            index = len(points) - 1
            if index >= 0:
                points.pop(index)
                success = True
                message = "Last pin removed!"
            else:
                success = False
                message = "No pin to remove!"
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

        if route is not None:
            if len(route["points"]) == 0:
                json_data["routes"].remove(route)

        with open(NautilusPilot.JSON_PATH, "w") as json_file:
            json.dump(json_data, json_file)

        self.update_kml()

        return success, message

    def __init__(self):
        self.driver = None
        self.canvas = None

        self.kml_profile_col_offset = 0
        self.kml_profile_row_offset = 0

    def screenshot(self):
        image_data = self.driver.get_screenshot_as_png()
        image = Image.open(io.BytesIO(image_data))
        # image.save("screenshot.png")
        image = np.array(image)

        return image

    def find_kml_profile(self, image):
        pixel_tolerance = 9
        gray_bar_color = np.array([225, 227, 225])
        white_color = np.array([255, 255, 255])
        kml_icon_color = np.array([68, 71, 70])

        height, width, _ = image.shape
        canvas_height, canvas_width = (
            self.canvas.size["height"],
            self.canvas.size["width"],
        )

        gray_bar_head_y = 0
        while (
            color_manhattan(image[gray_bar_head_y, width // 2], gray_bar_color)
            > pixel_tolerance
        ):
            gray_bar_head_y += 1

        gray_bar_head_x = width // 2
        while (
            color_manhattan(image[gray_bar_head_y, gray_bar_head_x], white_color)
            > pixel_tolerance
        ):
            gray_bar_head_x -= 2

        while (
            color_manhattan(image[gray_bar_head_y, gray_bar_head_x], kml_icon_color)
            > pixel_tolerance
        ):
            gray_bar_head_y += 2
            gray_bar_head_x += 2

        col = gray_bar_head_x
        row = gray_bar_head_y

        col = int(round(col * canvas_width / width))
        row = int(round(row * canvas_height / height))

        col_offset = col - canvas_width // 2
        row_offset = row - canvas_height // 2

        self.kml_profile_col_offset = col_offset
        self.kml_profile_row_offset = row_offset

    def update(self, is_first=False):
        if self.driver is None or self.canvas is None:
            return

        if is_first:
            image = self.screenshot()
            self.find_kml_profile(image)

        if not is_first:
            ActionChains(self.driver).send_keys("\ue00c").perform()
            ActionChains(self.driver).send_keys("\ue00c").perform()
            ActionChains(self.driver).send_keys("\ue00c").perform()

        with open(NautilusPilot.KML_PATH, mode="r") as file:
            content = file.read()
            b64_content = base64.b64encode(content.encode()).decode()

        self.driver.execute_script(
            NautilusPilot.JS_DRAG_AND_DROP.format(
                b64_content, os.path.basename(NautilusPilot.KML_PATH)
            ),
            self.canvas,
        )

        sleep(0.3)
        ActionChains(self.driver).move_to_element_with_offset(
            self.canvas, self.kml_profile_col_offset, self.kml_profile_row_offset
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

        sleep(3)
        WebDriverWait(self.driver, 30).until(
            lambda driver: driver.current_url.find("@") != -1
        )

        self.canvas = self.driver.find_element(By.ID, "earth-canvas")
        # self.canvas.click()

        self.update_kml()
        self.update(is_first=True)

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

        #pin-route-input {
            width: 44;
            margin-right: 2;
        }

        #pin-latitude-input {
            width: 46;
        }

        #pin-longitude-input {
            width: 46;
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
                    Label("    Route:", classes="pin-form-label"),
                    Input(id="pin-route-input", type="text"),
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

        #remove-route-input {
            width: 44;
            margin-right: 2;
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
                    Label("    Route:", classes="pin-form-label"),
                    Input(id="remove-route-input", type="text"),
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
        self.route_input = self.query_one("#pin-route-input")

        self.latitude_degress_input = self.query_one("#latitude-degree-input")
        self.latitude_minutes_input = self.query_one("#latitude-minute-input")
        self.latitude_direction_switch = self.query_one("#latitude-direction-switch")

        self.longitude_degress_input = self.query_one("#longitude-degree-input")
        self.longitude_minutes_input = self.query_one("#longitude-minute-input")
        self.longitude_direction_switch = self.query_one("#longitude-direction-switch")

        self.add_pin_button = self.query_one("#add-pin-button")
        self.cancel_pin_button = self.query_one("#cancel-pin-button")

        self.new_pin_form_focusables = [
            self.name_input,
            self.route_input,
            self.latitude_degress_input,
            self.latitude_minutes_input,
            self.latitude_direction_switch,
            self.longitude_degress_input,
            self.longitude_minutes_input,
            self.longitude_direction_switch,
            self.add_pin_button,
            self.cancel_pin_button,
        ]

        ### remove pin form
        self.remove_pin_form = self.query_one(Wheelhouse.RemovePinForm)
        self.remove_pin_form.visible = False
        self.remove_name_input = self.query_one("#remove-name-input")
        self.remove_route_input = self.query_one("#remove-route-input")
        self.remove_button = self.query_one("#remove-button")
        self.cancel_remove_button = self.query_one("#cancel-remove-button")

        self.remove_pin_form_focusables = [
            self.remove_name_input,
            self.remove_route_input,
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
                    go_up_cheatsheet = [0, 0, 1, 1, 1, 2, 3, 4, 5, 5]
                    current_focus = self.current_focus()
                    self.focusables[go_up_cheatsheet[current_focus]].focus()
                elif self.state == Wheelhouse.State.REMOVE_PIN:
                    go_up_cheatsheet = [0, 0, 1, 1]
                    current_focus = self.current_focus()
                    self.focusables[go_up_cheatsheet[current_focus]].focus()
                else:
                    self.previous_focus()

            case "down":
                if self.state == Wheelhouse.State.NEW_PIN:
                    go_down_cheatsheet = [1, 2, 5, 6, 7, 8, 8, 8, 9, 9]
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
        self.route_input.value = ""
        self.latitude_degress_input.value = ""
        self.latitude_minutes_input.value = ""
        self.latitude_direction_switch.value = False
        self.longitude_degress_input.value = ""
        self.longitude_minutes_input.value = ""
        self.longitude_direction_switch.value = False

        self.name_input.refresh()
        self.route_input.refresh()
        self.latitude_degress_input.refresh()
        self.latitude_minutes_input.refresh()
        self.latitude_direction_switch.refresh()
        self.longitude_degress_input.refresh()
        self.longitude_minutes_input.refresh()
        self.longitude_direction_switch.refresh()

    def add_pin(self):
        try:
            name = self.name_input.value
            route = self.route_input.value

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

            self.natpi.add_point(name, route, latitude, longitude)

        except Exception:
            return False
        else:
            return True

    ###########################################################################################
    ### remove pin form funtions ##############################################################

    def clear_remove_pin_form(self):
        self.remove_name_input.value = ""
        self.remove_route_input.value = ""

        self.remove_name_input.refresh()
        self.remove_route_input.refresh()

    def remove_pin(self):
        try:
            name = self.remove_name_input.value
            route = self.remove_route_input.value
            message = self.natpi.remove_point(name, route)
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
