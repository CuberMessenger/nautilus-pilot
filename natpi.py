import os
import json
import base64

import io

import simplekml
import numpy as np

from PIL import Image
from time import sleep

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.edge.service import Service


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

    def screenshot(self):
        image_data = self.driver.get_screenshot_as_png()
        image = Image.open(io.BytesIO(image_data))
        image = np.array(image)

        return image

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

        WebDriverWait(self.driver, 30).until(
            lambda driver: driver.current_url.find("@") != -1
        )

        self.canvas = self.driver.find_element(By.ID, "earth-canvas")
        self.canvas.click()
        self.update(is_first=True)

    def stop_browser(self):
        self.driver.quit()
        self.driver = None
        self.canvas = None
