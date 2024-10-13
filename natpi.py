import os
import time
import json
import base64
import argparse

import io
import cv2

import blessed
import threading
import simplekml
import numpy as np

from PIL import Image
from enum import Enum, auto

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.edge.service import Service


def json_to_kml(json_path, kml_path):
    with open(json_path, "r") as json_file:
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

    kml.save(kml_path)


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

    def __init__(self):
        self.driver = None
        self.canvas = None

    def find_sidebar_button(self):
        pixel_tolerance = 5
        default_gray = np.array([70, 71, 68])

        image_data = self.driver.get_screenshot_as_png()
        image = Image.open(io.BytesIO(image_data))
        image = np.array(image)

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

        if col == 0:
            raise Exception("Could not find the sidebar button!")

        is_open = col > top_bar_height

        col = int(round(col * canvas_width / width))
        row = int(round(row * canvas_height / height))

        col_offset = col - canvas_width // 2
        row_offset = row - canvas_height // 2
        return col_offset, row_offset, is_open

    def update_kml(self):
        json_path = r"data.json"
        kml_path = r"data.kml"
        json_to_kml(json_path, kml_path)

        with open(kml_path, mode="r") as file:
            content = file.read()
            b64_content = base64.b64encode(content.encode()).decode()

        col_offset, row_offset, is_open = self.find_sidebar_button()

        if not is_open:
            # Open the sidebar
            ActionChains(self.driver).move_to_element_with_offset(
                self.canvas, col_offset, row_offset
            ).click().perform()

        self.driver.execute_script(
            NautilusPilot.JS_DRAG_AND_DROP.format(
                b64_content, os.path.basename(kml_path)
            ),
            self.canvas,
        )

        if not is_open:
            col_offset, row_offset, is_open = self.find_sidebar_button()

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

        WebDriverWait(self.driver, 30).until(
            lambda driver: driver.current_url.find("@") != -1
        )

        self.canvas = self.driver.find_element(By.ID, "earth-canvas")
        self.canvas.click()

    def stop_browser(self):
        self.driver.quit()
        self.driver = None
        self.canvas = None


class Wheelhouse:
    class State(Enum):
        MENU = auto()
        NEW_PIN_DIALOG = auto()
        NEW_WAYPOINT_DIALOG = auto()
        DEL_WAYPOINT_DIALOG = auto()

    def __init__(self):
        self.terminal = blessed.Terminal()
        self.natpi = NautilusPilot()
        self.state = Wheelhouse.State.MENU

        # Menu
        self.is_online = False
        self.options = [
            "Switch",
            "Add pin",
            "Add way point",
            "Remove the last way point",
            "Leave",
        ]
        self.num_options = len(self.options)
        self.selected_option = 0

        self.running_flag = True
        self.listen_flag = True
        self.resize_thread = threading.Thread(target=self.resize_listener)

        # New pin dialog
        self.reset_new_pin_dialog()

        # New way point dialog
        pass

        # Del way point dialog
        pass

        self.measure_terminal()

    def reset_new_pin_dialog(self):
        self.new_pin_active_line = 0
        self.new_pin_offsets = [0, 0, 0]
        self.new_pin_num_lines = 3
        self.new_pin_dirty = [True, True, True]
        self.new_pin_heads = ["Name:      ", "Latitude:  ", "Longitude: "]
        self.new_pin_lines = [
            "______________",
            "___.__°, __' N",
            "___.__°, __' E",
        ]

    def resize_listener(self):
        while self.listen_flag:
            time.sleep(0.1)
            if self.terminal.width != self.width or self.terminal.height != self.height:
                self.measure_terminal()
                self.draw_all()

    def measure_terminal(self):
        self.width = self.terminal.width
        self.height = self.terminal.height

        self.chamber_width = int(self.width * 0.8)
        self.chamber_height = int(self.height * 0.8)

        self.chamber_start_x = (self.width - self.chamber_width) // 2
        self.chamber_start_y = (self.height - self.chamber_height) // 2
        self.chamber_end_x = self.chamber_start_x + self.chamber_width
        self.chamber_end_y = self.chamber_start_y + self.chamber_height

        horizontal_start = self.width // 2 - 10

        self.status_x = horizontal_start
        self.status_y = self.chamber_start_y + 2

        self.options_x = horizontal_start
        self.options_y = self.status_y + 2

        self.inputs_x = horizontal_start
        self.inputs_y = self.options_y + self.num_options + 2

    def draw_chamber(self):
        horizontal_line = "-" * (self.chamber_width - 2)

        title = "Nautilus Wheelhouse"
        title = f"-- {title} --"
        start_title_pos = (self.chamber_width - len(title)) // 2
        top_border = f"+{horizontal_line[:start_title_pos]}{title}{horizontal_line[start_title_pos + len(title):]}+"

        bottom_border = "+" + "-" * (self.chamber_width - 2) + "+"

        print(
            self.terminal.move_xy(self.chamber_start_x, self.chamber_start_y)
            + top_border
        )

        for i in range(1, self.chamber_height):
            print(
                self.terminal.move_xy(self.chamber_start_x, self.chamber_start_y + i)
                + f"|{' ' * (self.chamber_width - 2)}|"
            )

        print(
            self.terminal.move_xy(self.chamber_start_x, self.chamber_end_y)
            + bottom_border
        )

    def draw_status(self, hourglass=False):
        if hourglass:
            status_line = f"Status: ⏳⏳⏳    "
        elif self.is_online:
            status_line = f"Status: {self.terminal.green}Online {self.terminal.normal}"
        else:
            status_line = f"Status: {self.terminal.red}Offline{self.terminal.normal}"
        print(self.terminal.move_xy(self.status_x, self.status_y) + status_line)

    def draw_options(self):
        for i, option in enumerate(self.options):
            if i == self.selected_option:
                print(
                    self.terminal.move_xy(self.options_x, self.options_y + i)
                    + f"{self.terminal.reverse}⭐ {option}{self.terminal.normal}"
                )
            else:
                print(
                    self.terminal.move_xy(self.options_x, self.options_y + i)
                    + f"⭐ {option}"
                )

    def flush_option_area(self):
        i = 0
        while i + self.options_y < self.chamber_end_y - 1:
            print(
                self.terminal.move_xy(self.chamber_start_x, self.options_y + i)
                + f"|{' ' * (self.chamber_width - 2)}|"
            )
            i += 1

    def draw_new_pin_dialog(self):
        for line_index in range(3):
            if not self.new_pin_dirty[line_index]:
                continue
            self.new_pin_dirty[line_index] = False

            head = self.new_pin_heads[line_index]
            line = self.new_pin_lines[line_index]
            if self.new_pin_active_line == line_index:
                offset = self.new_pin_offsets[line_index]
                line = f"{line[:offset]}{self.terminal.reverse}{line[offset]}{self.terminal.normal}{line[offset + 1:]}"

            print(
                self.terminal.move_xy(self.options_x, self.options_y + line_index)
                + head
                + line
            )

        helpers = [
            f"{self.terminal.skyblue}UP/DOWN   - move{self.terminal.normal}",
            f"{self.terminal.skyblue}TAB       - switch N/S and E/W{self.terminal.normal}",
            f"{self.terminal.skyblue}ENTER     - save{self.terminal.normal}",
            f"{self.terminal.skyblue}ESC       - cancel{self.terminal.normal}",
        ]

        for i, helper in enumerate(helpers):
            print(
                self.terminal.move_xy(self.options_x, self.options_y + 4 + i) + helper
            )

    def draw_all(self):
        print(self.terminal.home + self.terminal.clear)
        match self.state:
            case Wheelhouse.State.MENU:
                self.draw_chamber()
                self.draw_status()
                self.draw_options()
            case Wheelhouse.State.NEW_PIN_DIALOG:
                self.draw_chamber()
                self.draw_status()
                self.draw_new_pin_dialog()
            case Wheelhouse.State.NEW_WAYPOINT_DIALOG:
                pass
            case Wheelhouse.State.DEL_WAYPOINT_DIALOG:
                pass
            case _:
                raise ValueError("Invalid state")

    def menu_handler(self, key):
        if key.code == self.terminal.KEY_ENTER:
            match self.selected_option:
                case 0:  # Switch
                    self.is_online = not self.is_online
                    if self.is_online:
                        self.draw_status(hourglass=True)

                        self.natpi.start_browser()
                        self.natpi.update_kml()
                    else:
                        self.draw_status(hourglass=True)
                        self.natpi.stop_browser()
                    self.draw_status()
                case 1:  # Add pin
                    self.state = Wheelhouse.State.NEW_PIN_DIALOG
                    self.flush_option_area()
                    self.draw_new_pin_dialog()
                case 2:  # Add way point
                    pass
                case 3:  # Remove the last way point
                    pass
                case 4:  # Leave
                    self.running_flag = False
                case _:
                    raise ValueError("Invalid option")
            return

        if key.code == self.terminal.KEY_DOWN:
            self.selected_option = min(self.selected_option + 1, self.num_options - 1)
            self.draw_options()
            return

        if key.code == self.terminal.KEY_UP:
            self.selected_option = max(self.selected_option - 1, 0)
            self.draw_options()
            return

    def new_pin_handler(self, key):
        if key.code == self.terminal.KEY_DOWN:
            self.new_pin_dirty[self.new_pin_active_line] = True
            self.new_pin_active_line = min(
                self.new_pin_active_line + 1, self.new_pin_num_lines - 1
            )
            self.new_pin_dirty[self.new_pin_active_line] = True
            self.draw_new_pin_dialog()
            return

        if key.code == self.terminal.KEY_UP:
            self.new_pin_dirty[self.new_pin_active_line] = True
            self.new_pin_active_line = max(self.new_pin_active_line - 1, 0)
            self.new_pin_dirty[self.new_pin_active_line] = True
            self.draw_new_pin_dialog()
            return

        if key.code == self.terminal.KEY_ESCAPE:
            self.reset_new_pin_dialog()
            self.state = Wheelhouse.State.MENU
            self.draw_all()
            return

        if key.code == self.terminal.KEY_TAB:
            if (self.new_pin_active_line == 1) and (
                self.new_pin_offsets[1] == len(self.new_pin_lines[1]) - 1
            ):
                if self.new_pin_lines[1][-1] == "N":
                    self.new_pin_lines[1] = self.new_pin_lines[1][:-1] + "S"
                else:
                    self.new_pin_lines[1] = self.new_pin_lines[1][:-1] + "N"
                self.new_pin_dirty[1] = True
                self.draw_new_pin_dialog()
                return

            if (self.new_pin_active_line == 2) and (
                self.new_pin_offsets[2] == len(self.new_pin_lines[2]) - 1
            ):
                if self.new_pin_lines[2][-1] == "E":
                    self.new_pin_lines[2] = self.new_pin_lines[2][:-1] + "W"
                else:
                    self.new_pin_lines[2] = self.new_pin_lines[2][:-1] + "E"
                self.new_pin_dirty[2] = True
                self.draw_new_pin_dialog()
                return
            
        if key.code == self.terminal.KEY_ENTER:
            # save
            self.reset_new_pin_dialog()
            self.state = Wheelhouse.State.MENU
            self.draw_all()
            return
        
        # numbers or letters
        

    def sail(self):
        try:
            self.resize_thread.start()

            with (
                self.terminal.fullscreen(),
                self.terminal.cbreak(),
                self.terminal.hidden_cursor(),
            ):
                self.draw_all()
                while self.running_flag:
                    key = self.terminal.inkey()
                    match self.state:
                        case Wheelhouse.State.MENU:
                            self.menu_handler(key)
                        case Wheelhouse.State.NEW_PIN_DIALOG:
                            self.new_pin_handler(key)
                        case Wheelhouse.State.NEW_WAYPOINT_DIALOG:
                            pass
                        case Wheelhouse.State.DEL_WAYPOINT_DIALOG:
                            pass
                        case _:
                            raise ValueError("Invalid state")

        except KeyboardInterrupt:
            pass
        finally:
            self.listen_flag = False
            self.resize_thread.join()


def main():
    wheelhouse = Wheelhouse()
    wheelhouse.sail()


if __name__ == "__main__":
    main()
